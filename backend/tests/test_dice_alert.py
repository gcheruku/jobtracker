"""Dice alert ingestion.

Dice alert emails (from dice@connect.dice.com) wrap every job in an opaque
click-tracker on elinks.dice.com with no decodable target URL. These must be
recognized as job-posting links so the tile extractor can parse them; nav links
(unsubscribe, etc.) must still be dropped by the tile-text skip markers.
"""
import base64

from app.services.email_parser import _is_job_posting, build_payload, provider_of

# Real tracker links from a Dice alert email (tokens are opaque redirects).
_WALMART = "https://elinks.dice.com/a/sc/nN2DaiZebeGk8nrn-qolsYgGOjW17pLO/_KlauZG1gk8xkYVupiV3bfFirvmWTU6C/22"
_MCKESSON = "https://elinks.dice.com/a/sc/YOXvdWunALzXtl15SL2IteRX1Ln2Tcay/wHBe1oz6Gs75YdXZs6K1VFkuv20Ro_-E/22"


class TestIsJobPosting:
    def test_accepts_dice_click_tracker(self):
        assert _is_job_posting(_WALMART)
        assert _is_job_posting(_MCKESSON)

    def test_still_accepts_direct_dice_links(self):
        assert _is_job_posting("https://www.dice.com/job-detail/abc-123")

    def test_rejects_non_posting_dice_url(self):
        # The bare tracker/home host with no posting path is not a job link.
        assert not _is_job_posting("https://www.dice.com/")

    def test_rejects_non_job_domain(self):
        assert not _is_job_posting("https://example.com/a/sc/whatever/22")


def _dice_message(html: str) -> dict:
    """Minimal Gmail message dict shaped like fetch_message() output."""
    data = base64.urlsafe_b64encode(html.encode("utf-8")).decode("ascii")
    return {
        "id": "msg-dice-1",
        "internalDate": "1720000000000",
        "payload": {
            "headers": [
                {"name": "From", "value": "Dice <dice@connect.dice.com>"},
                {"name": "Subject", "value": "New jobs matching your search"},
                {"name": "Message-Id", "value": "<abc@connect.dice.com>"},
            ],
            "mimeType": "text/html",
            "body": {"data": data},
        },
    }


class TestBuildPayloadDice:
    def test_extracts_job_links_drops_unsubscribe(self):
        html = f"""
        <html><body>
          <div id="jobs">
            <div class="tile">
              <a href="{_WALMART}">Senior Software Engineer</a>
              <div>Walmart</div><div>Bentonville, AR</div>
            </div>
            <div class="tile">
              <a href="{_MCKESSON}">Staff Data Engineer</a>
              <div>McKesson</div><div>Irving, TX</div>
            </div>
          </div>
          <div class="footer">
            <a href="https://elinks.dice.com/a/sc/zzz/yyy/99">Unsubscribe</a>
          </div>
        </body></html>
        """
        payload = build_payload(_dice_message(html))
        assert payload.provider == "Dice"
        urls = {link["url"] for link in payload.links}
        assert _WALMART in urls
        assert _MCKESSON in urls
        # Nav link is a tracker too, but its tile text hits a skip marker.
        assert all("/99" not in u for u in urls)
        # Tile text carries the title/company for the LLM extractor.
        walmart_tile = next(l["text"] for l in payload.links if l["url"] == _WALMART)
        assert "Senior Software Engineer" in walmart_tile
        assert "Walmart" in walmart_tile


def test_provider_of_dice_sender():
    assert provider_of("Dice <dice@connect.dice.com>") == "Dice"
