from pyppeteer import launch

_browser = None


async def get_browser():
    global _browser

    if _browser is None:
        _browser = await launch(autoClose=False, headless=False)

    return _browser
