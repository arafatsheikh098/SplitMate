"""CSV export tests (M7 A2)."""

from __future__ import annotations

import csv
import io
import re

from fastapi.testclient import TestClient

from splitmate.services.csv_export import (
    csv_response_body,
    expenses_csv,
    settlements_csv,
)


def _seed_via_service(session) -> int:
    """Create a group via the service, add an expense with a formula title."""
    from splitmate import services
    from splitmate.services.expenses import create_expense

    g, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    bea = services.join_group(session, group=g, display_name="Bea")
    create_expense(
        session,
        group_id=g.id,
        creator_id=admin.id,
        data={
            "title": "=SUM(A1:A99)",
            "amount": "10.00",
            "date": "2025-01-01",
            "category": "Other",
            "split_method": "equal",
            "participants": [str(admin.id), str(bea.id)],
            "payer_id": str(admin.id),
            "payer_amount": "10.00",
        },
    )
    return g.id


def test_csv_neutralises_formula_prefixes(session) -> None:
    gid = _seed_via_service(session)
    csv_text = expenses_csv(session, group_id=gid)
    # The unquoted formula `=SUM(...)` must never appear.  The only
    # allowed form is the neutralised `' =SUM(...)`.
    import re

    # Look for `,=SUM` or `<start>=SUM` — both indicate an unquoted formula.
    assert not re.search(r"(?:^|,)=SUM", csv_text), csv_text
    # The neutralised title must appear (single quote prefix).
    assert "'=SUM(A1:A99)" in csv_text


def test_csv_parses_with_csv_module(session) -> None:
    gid = _seed_via_service(session)
    csv_text = expenses_csv(session, group_id=gid)
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0][0] == "date"
    # The data row must contain the neutralised title in the title column.
    assert any(
        cell == "'=SUM(A1:A99)" for row in rows[1:] for cell in row
    )


def test_csv_response_includes_bom() -> None:
    body = csv_response_body("hello\n")
    assert body.startswith(b"\xef\xbb\xbf")
    assert body.endswith(b"hello\n")


def test_settlements_csv_runs(session) -> None:
    from splitmate import services
    from splitmate.services.settlements import create_settlement

    g, admin, _ = services.create_group(
        session, name="Trip", currency_symbol="৳", admin_name="Asha"
    )
    bea = services.join_group(session, group=g, display_name="Bea")
    create_settlement(
        session,
        group_id=g.id,
        creator_id=admin.id,
        data={
            "from_id": str(bea.id),
            "to_id": str(admin.id),
            "amount": "3.00",
            "method": "cash",
            "date": "2025-01-01",
            "note": "",
        },
    )
    csv_text = settlements_csv(session, group_id=g.id)
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0] == [
        "date",
        "from",
        "to",
        "amount",
        "currency",
        "method",
        "note",
    ]
    assert len(rows) >= 2
    assert rows[1][3] == "3.00"


def test_csv_endpoint_returns_attachment(session) -> None:
    """HTTP-level: the route serves CSV with the right headers."""
    # Set up via service to populate the same database the TestClient will use.
    _seed_via_service(session)
    # Create a new client (the test-session engine is shared via tmp_path).
    from splitmate.main import create_app

    with TestClient(create_app()) as c:
        # Log in by creating a throwaway group (so the cookie is set),
        # then re-use the data we already have.  The simplest path is to
        # log in via the /groups/new form, which the existing admin tests
        # use to authenticate.
        r = c.post(
            "/groups/new",
            data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
        )
        assert r.status_code == 200
        new_gid = int(re.search(r"/groups/(\d+)", r.text).group(1))
        r = c.get(f"/groups/{new_gid}/expenses.csv")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers.get("content-disposition", "")
        # The body must start with a UTF-8 BOM (Excel-friendly).
        assert r.content.startswith(b"\xef\xbb\xbf")
        # And contain the header row.
        assert r.text.lstrip("\ufeff").startswith("date,title,")
        # The seeded group's expenses aren't in this group, so we only
        # verify the structural contract.  Direct service-level test
        # already proves data correctness.


def test_csv_endpoint_404_for_unauthenticated(client) -> None:
    r = client.get("/groups/99999/expenses.csv")
    assert r.status_code in (401, 403, 404)
