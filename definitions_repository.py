from fastapi import FastAPI, HTTPException, Query
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel
import uuid
from azure.cosmos import CosmosClient, PartitionKey, DatabaseProxy
from datetime import datetime
import random

app = FastAPI()

class Author(BaseModel):
    name: str

class Definition(BaseModel):
    id: Optional[str] = None
    word: str
    content: str
    tag: str
    abbreviation: str
    author: Author
    created_date: Optional[datetime] = None


class PaginatedResponse(BaseModel):
    data: List[Any]
    continuation_token: Optional[str] = None

class DefinitionsRepository:
    def __init__(self, database: DatabaseProxy, definitions_container: str):
        self.definitions = database.get_container_client(definitions_container)
        self.max_page_size = 50

    async def get_all_definitions(self, page_size: int = 10, continuation_token: Optional[str] = None) -> Tuple[List[Definition], Optional[str]]:
        page_size = min(page_size, self.max_page_size)
        query = "SELECT * FROM c"
        return await self._query_with_paging(query, page_size, continuation_token)

    async def get_definition_by_id(self, id: str, word: str) -> Optional[Definition]:
        try:
            result = self.definitions.read_item(id, partition_key=word)
            return Definition(**result)
        except:
            return None


    async def get_definition_by_word(self, word: str) -> Optional[Definition]:
        query = "SELECT * FROM d WHERE LOWER(d.word) = @word"
        params = [{"name": "@word", "value": word.lower()}]
        results = list(self.definitions.query_items(query, parameters=params))
        return Definition(**results[0]) if results else None

    async def get_definitions_by_tag(self, tag: str, page_size: int = 5, continuation_token: Optional[str] = None) -> Tuple[List[Definition], Optional[str]]:
        query = "SELECT * FROM d WHERE LOWER(d.tag) = @tag"
        params = [{"name": "@tag", "value": tag.lower()}]
        return await self._query_with_paging(query, page_size, continuation_token, params)

    async def delete_definition(self, definition: Definition):
        self.definitions.delete_item(definition.id, partition_key=definition.word)

    async def add_definition(self, definition: Definition):
        definition.id = str(uuid.uuid4())
        definition.created_date = datetime.utcnow()
        self.definitions.create_item(definition.dict())

    async def update_definition(self, definition: Definition):
        self.definitions.replace_item(definition.id, definition.dict(), partition_key=definition.word)

    async def get_definitions_by_search(self, search_term: str, page_size: int = 10, continuation_token: Optional[str] = None) -> Tuple[List[Definition], Optional[str]]:
        query = """
        SELECT * FROM d WHERE 
        LOWER(d.word) LIKE @search OR
        LOWER(d.content) LIKE @search OR
        LOWER(d.author.name) LIKE @search OR
        LOWER(d.tag) LIKE @search OR
        LOWER(d.abbreviation) LIKE @search
        """
        params = [{"name": "@search", "value": f"%{search_term.lower()}%"}]
        return await self._query_with_paging(query, page_size, continuation_token, params)

    async def get_random_definition(self) -> Optional[Definition]:
        count = await self.get_definition_count()
        if count == 0:
            return None
        skip = random.randint(0, count - 1)
        query = f"SELECT * FROM c OFFSET {skip} LIMIT 1"
        results = list(self.definitions.query_items(query))
        return Definition(**results[0]) if results else None

    async def get_definition_count(self) -> int:
        query = "SELECT VALUE COUNT(1) FROM c"
        return list(self.definitions.query_items(query))[0]

    async def _query_with_paging(self, query: str, page_size: int, continuation_token: Optional[str] = None, params: List[Dict] = None) -> Tuple[List[Any], Optional[str]]:
        options = {
            "max_item_count": page_size,
            "continuation_token": continuation_token
        }
        
        results = []
        query_iterator = self.definitions.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        )
        
        for item in query_iterator:
            results.append(item)
            if len(results) >= page_size:
                break
                
        return results, getattr(query_iterator, '_continuation_token', None)