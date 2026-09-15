import copy
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base_all import Base
from app.db.session import get_db
from app.db.mongodb import set_test_mongo_db
from app.main import app
from app.worker.celery_app import celery_app

# Configure Celery for testing (execute in-memory without requiring external Redis broker)
celery_app.conf.update(
    task_always_eager=True,
)

# SQLite in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# In-Memory Mock MongoDB & GridFS for Fast, Offline Pytest Test Runs
# ---------------------------------------------------------------------------

class MockCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        if length is not None:
            return copy.deepcopy(self._docs[:length])
        return copy.deepcopy(self._docs)


class MockCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "$and":
                if not all(self._matches(doc, q) for q in v):
                    return False
                continue
            if k == "$or":
                if not any(self._matches(doc, q) for q in v):
                    return False
                continue
            if isinstance(v, dict):
                if "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                elif "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def find_one(self, query):
        for d in self.docs:
            if self._matches(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query):
        matched = [d for d in self.docs if self._matches(d, query)]
        return MockCursor(matched)

    async def insert_one(self, doc):
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        d = copy.deepcopy(doc)
        self.docs.append(d)
        class InsertResult:
            inserted_id = d["_id"]
        return InsertResult()

    async def update_one(self, query, update, upsert=False):
        matched_idx = -1
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                matched_idx = i
                break

        class UpdateResult:
            matched_count = 0
            modified_count = 0

        res = UpdateResult()
        if matched_idx >= 0:
            res.matched_count = 1
            res.modified_count = 1
            if "$set" in update:
                self.docs[matched_idx].update(copy.deepcopy(update["$set"]))
        elif upsert:
            new_doc = copy.deepcopy(query)
            new_doc["_id"] = ObjectId()
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            self.docs.append(new_doc)
            res.modified_count = 1
        return res

    async def update_many(self, query, update):
        count = 0
        for d in self.docs:
            if self._matches(d, query):
                count += 1
                if "$set" in update:
                    d.update(copy.deepcopy(update["$set"]))
        class UpdateManyResult:
            matched_count = count
            modified_count = count
        return UpdateManyResult()

    async def delete_one(self, query):
        initial_len = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, query)]
        class DeleteResult:
            deleted_count = initial_len - len(self.docs)
        return DeleteResult()

    async def count_documents(self, query):
        return sum(1 for d in self.docs if self._matches(d, query))

    async def create_index(self, *args, **kwargs):
        return "index_ok"


class MockGridOut:
    def __init__(self, data):
        self._data = data
        self._consumed = False

    async def readchunk(self):
        if not self._consumed:
            self._consumed = True
            return self._data
        return b""

    async def read(self):
        return self._data


class MockUploadStream:
    def __init__(self, bucket, filename, metadata=None):
        self.bucket = bucket
        self.filename = filename
        self.metadata = metadata
        self._id = ObjectId()
        self.buffer = bytearray()

    async def write(self, data):
        self.buffer.extend(data)

    async def close(self):
        self.bucket.files[str(self._id)] = bytes(self.buffer)


class MockGridFSBucket:
    def __init__(self):
        self.files = {}

    def open_upload_stream(self, filename, metadata=None):
        return MockUploadStream(self, filename, metadata)

    async def open_download_stream(self, file_id):
        fid = str(file_id)
        if fid not in self.files:
            raise KeyError(f"File {file_id} not found in GridFS")
        return MockGridOut(self.files[fid])

    async def delete(self, file_id):
        fid = str(file_id)
        if fid in self.files:
            del self.files[fid]


class MockMongoDatabase:
    def __init__(self):
        self.collections = {}
        self._gridfs_bucket = MockGridFSBucket()

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]

    async def command(self, cmd, *args, **kwargs):
        return {"ok": 1}


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test function."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True, scope="function")
def auto_mock_mongo():
    """Ensure every test uses in-memory mock MongoDB without network latency."""
    mock_mongo = MockMongoDatabase()
    set_test_mongo_db(mock_mongo)
    yield mock_mongo
    set_test_mongo_db(None)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden database and in-memory MongoDB dependencies."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()

