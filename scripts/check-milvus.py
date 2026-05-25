"""Check Milvus collection data and metadata."""
import sys
from pymilvus import MilvusClient

host = sys.argv[1] if len(sys.argv) > 1 else "http://milvus.data-strat-poc.svc.cluster.local:19530"
client = MilvusClient(uri=host)
collections = client.list_collections()
print("Collections:", collections)

for c in collections:
    print(f"\n=== {c} ===")
    desc = client.describe_collection(c)
    fields = [f["name"] for f in desc.get("fields", [])]
    print("Fields:", fields)

    output_fields = [f for f in fields if f != "embedding"]
    try:
        results = client.query(
            collection_name=c, filter="", limit=3,
            output_fields=output_fields,
        )
        for i, r in enumerate(results):
            print(f"\n  --- chunk {i} ---")
            for k in output_fields:
                val = r.get(k, "")
                if k == "text":
                    val = str(val)[:100] + "..."
                print(f"  {k}: {val}")
    except Exception as e:
        print(f"  query error: {e}")
