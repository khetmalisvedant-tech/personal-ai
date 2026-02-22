from fastapi import FastAPI
from main import router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

def run_cli():
    print("🔥 Personal AI Agent Started")
    print("Type exit to quit\n")

    from engine import AIEngine
    engine = AIEngine()

    while True:
        command = input(">>> ")

        if command.lower() == "exit":
            break

        response = engine.chat(command)
        print(response)


if __name__ == "__main__":
    run_cli()