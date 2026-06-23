import chromadb
from chromadb.config import Settings

from .database import get_seed_employees


def make_chroma_client(path: str = "./chromadb") -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=path)


def make_ephemeral_client() -> chromadb.ClientAPI:
    return chromadb.EphemeralClient()


def init_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    return client.get_or_create_collection("employee_cvs")


def seed_collection(collection: chromadb.Collection) -> None:
    seed_employees = get_seed_employees()
    existing = set(collection.get(ids=[e["id"] for e in seed_employees])["ids"])
    to_add = [e for e in seed_employees if e["id"] not in existing]
    if not to_add:
        return
    collection.add(
        ids=[e["id"] for e in to_add],
        documents=[e["cv_text"] for e in to_add],
        metadatas=[{"name": e["name"], "reply_company": e["reply_company"]} for e in to_add],
    )
