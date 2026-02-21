from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from multi_task import WebAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str
    mode: int


@app.post("/query")
async def handle_query(request: QueryRequest):
    try:
        agent = WebAgent()
        result = await agent.run(request.query)

        if result.get("status") == "success":
            return result.get("answer")
        return result
    except Exception as e:
        return {"error": f"Server Error: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007, reload=False)
