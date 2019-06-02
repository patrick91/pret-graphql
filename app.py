import uvicorn
from starlette.applications import Starlette
from strawberry.contrib.starlette import GraphQLApp

from schema import schema


from browser import get_browser

app = Starlette()
app.debug = False

app.add_route("/graphql", GraphQLApp(schema))


@app.on_event("startup")
async def startup():
    await get_browser()


@app.on_event("shutdown")
async def shutdown():
    browser = await get_browser()
    await browser.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
