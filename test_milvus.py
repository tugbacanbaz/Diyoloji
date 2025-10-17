from src.vector_milvus import connect, ensure_collection
from src.config import settings
from pymilvus import utility

def test_milvus_connection():
    print("Testing Milvus connection...")
    try:
        # Try to connect
        connect()
        print("✅ Successfully connected to Milvus")
        
        # List collections
        collections = utility.list_collections()
        print(f"\nAvailable collections: {collections}")
        
        if settings.milvus_collection in collections:
            # Get collection info
            collection = ensure_collection(settings.milvus_dim)
            row_count = collection.num_entities
            print(f"\nCollection info for {settings.milvus_collection}:")
            print(f"Row count: {row_count}")
            
            # Try a simple search
            if row_count > 0:
                print("\nTesting search functionality...")
                collection.load()
                results = collection.query(
                    expr=f"{settings.milvus_text_field} like '%'",
                    output_fields=[settings.milvus_text_field],
                    limit=1
                )
                if results:
                    print("✅ Successfully retrieved a sample document:")
                    print(f"Sample text: {results[0][settings.milvus_text_field][:200]}...")
                else:
                    print("⚠️ No documents found in the collection")
        else:
            print(f"\n⚠️ Collection {settings.milvus_collection} not found")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

if __name__ == "__main__":
    test_milvus_connection()