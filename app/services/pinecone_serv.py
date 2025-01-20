import time
from pinecone import Pinecone, ServerlessSpec, Index, Vector
from sentence_transformers import SentenceTransformer
from app.config import PINECONE_API_KEY, PINECONE_INDEX


class PineconeService:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    index_name = PINECONE_INDEX

    def __create_pc_index(self) -> None:
        self.pc.create_index(
            name=self.index_name,
            dimension=384,
            spec=ServerlessSpec(
                cloud='aws', 
                region='us-east-1'
            ) 
        )

    def __get_pc_index(self) -> Index:
        if self.index_name not in self.pc.list_indexes().names():
            self.__create_pc_index()
            time.sleep(1)
        return self.pc.Index(self.index_name)
    
    def __get_list_of_chunks(self, text: str, chunk_size: int = 1050, overlap: int = 50) -> list[str]:
        """
        Splits text into chunks of a specific size with optional overlap.
        Args:
            text (str): The text to split.
            chunk_size (int): The number of characters per chunk.
            overlap (int): The number of overlapping characters between chunks.
        Returns:
            list: A list of text chunks.
        """
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunks.append(text[i:i + chunk_size])
        return chunks
    
    def upload_embeddings(self, document_data: str, document_id: str) -> None:
        # Each contains an 'id', the embedding 'values', and the original text as 'metadata'
        chunks: list[str] = self.__get_list_of_chunks(document_data)
        pc_index = self.__get_pc_index()
        vectors = []
        for i, chunk in enumerate(chunks):
            embedding = self.model.encode(chunk).tolist()
            vector_id = f"{document_id}_{i}"  # Unique ID for each chunk
            vectors.append(
                Vector(
                    id=vector_id,
                    values=embedding,
                    metadata={"text": chunk, "doc_id": document_id}
                )
            )

        pc_index.upsert(vectors=vectors, namespace="docs-ns")

    def get_matched_embeddings(self, query: str):
        query_embedding = self.model.encode(query).tolist()
        pc_index = self.__get_pc_index()
        results = pc_index.query(
            namespace="docs-ns",
            vector=query_embedding,
            top_k=3,
            include_values=False,
            include_metadata=True
        )
        return results
