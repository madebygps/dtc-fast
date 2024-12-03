from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import logging
import os
from azure.cosmos import CosmosClient
from azure.cosmos.database import DatabaseProxy
from definitions_repository import Definition, PaginatedResponse, DefinitionsRepository
from typing import Optional

load_dotenv()

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dictionary")

def get_cosmos_client() -> CosmosClient:
    return CosmosClient(os.getenv("AZURE_COSMOS_ENDPOINT"), os.getenv("AZURE_COSMOS_KEY"))

def get_cosmos_database(client: CosmosClient = Depends(get_cosmos_client)) -> DatabaseProxy:
    return client.get_database_client(os.getenv("AZURE_COSMOS_DATABASE_NAME"))

def get_repository(database: DatabaseProxy = Depends(get_cosmos_database)) -> DefinitionsRepository:
    return DefinitionsRepository(
        database,
        os.getenv("AZURE_COSMOS_CONTAINER_NAME")
    )
    
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/definitions", response_model=PaginatedResponse)
async def get_all_definitions(
    page_size: int = Query(10, le=50),
    continuation_token: Optional[str] = None,
    repo: DefinitionsRepository = Depends(get_repository)
):
    definitions, token = await repo.get_all_definitions(page_size, continuation_token)
    if not definitions:
        raise HTTPException(status_code=404, detail="No definitions found")
    return PaginatedResponse(data=definitions, continuation_token=token)

@app.get("/definitions/{id}")
async def get_definition_by_id(
    id: str,
    word: str,
    repo: DefinitionsRepository = Depends(get_repository)
):
    definition = await repo.get_definition_by_id(id, word)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Definition with ID {id} not found")
    return definition

@app.get("/definitions/word/{word}")
async def get_definition_by_word(
    word: str,
    repo: DefinitionsRepository = Depends(get_repository)
):
    definition = await repo.get_definition_by_word(word)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Definition for word '{word}' not found")
    return definition


@app.get("/definitions/tag/{tag}", response_model=PaginatedResponse)
async def get_definitions_by_tag(
    tag: str,
    page_size: int = Query(5, le=50),
    continuation_token: Optional[str] = None,
    repo: DefinitionsRepository = Depends(get_repository)
):
    definitions, token = await repo.get_definitions_by_tag(tag, page_size, continuation_token)
    if not definitions:
        raise HTTPException(status_code=404, detail=f"No definitions found for tag '{tag}'")
    return PaginatedResponse(data=definitions, continuation_token=token)

@app.get("/definitions/search/{term}", response_model=PaginatedResponse)
async def search_definitions(
    term: str,
    page_size: int = Query(10, le=50),
    continuation_token: Optional[str] = None,
    repo: DefinitionsRepository = Depends(get_repository)
):
    definitions, token = await repo.get_definitions_by_search(term, page_size, continuation_token)
    if not definitions:
        raise HTTPException(status_code=404, detail=f"No definitions found for search term '{term}'")
    return PaginatedResponse(data=definitions, continuation_token=token)

@app.delete("/definitions/{word}")
async def delete_definition(
    word: str,
    repo: DefinitionsRepository = Depends(get_repository)
):
    definition = await repo.get_definition_by_word(word)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Definition for word '{word}' not found")
    await repo.delete_definition(definition)
    return {"status": "deleted"}

@app.post("/definitions", status_code=201)
async def create_definition(
    definition: Definition,
    repo: DefinitionsRepository = Depends(get_repository)
):
    existing = await repo.get_definition_by_word(definition.word)
    if existing:
        raise HTTPException(status_code=409, detail=f"Definition for word '{definition.word}' already exists")
    await repo.add_definition(definition)
    return definition

@app.put("/definitions/{word}")
async def update_definition(
    word: str,
    definition: Definition,
    repo: DefinitionsRepository = Depends(get_repository)
):
    existing = await repo.get_definition_by_word(word)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Definition for word '{word}' not found")
    await repo.update_definition(definition)
    return definition