import requests


class HTTPClient:

    def __init__(
        self,
        timeout=30,
    ):
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/139.0 Safari/537.36"
            )
        })

    def get(self, url, **kwargs):

        response = self.session.get(
            url,
            timeout=self.timeout,
            **kwargs,
        )

        response.raise_for_status()

        return response