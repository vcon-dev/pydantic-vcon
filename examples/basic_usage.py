"""
Basic usage example of pydantic-vcon (vCon core-05, syntax 0.5.0)
"""

from datetime import datetime, timezone

from pydantic_vcon import (
    Analysis,
    CivicAddress,
    Dialog,
    DialogType,
    Encoding,
    Event,
    Party,
    VCon,
)


def main():
    vcon = VCon.build_new()

    # Parties: the sender first, then the receiver
    vcon.add_party(
        Party(
            tel="+1234567890",
            name="John Doe",
            civicaddress=CivicAddress(country="US", a1="CA", a3="San Francisco"),
        )
    )
    vcon.add_party(Party(mailto="agent@example.com", name="Agent"))

    now = datetime.now(timezone.utc).isoformat()

    # A text dialog. parties lists the contributors only; the receivers are in the
    # Session, which add_dialog creates (or reuses) and which lists this dialog.
    vcon.add_dialog(
        Dialog(
            type=DialogType.TEXT,
            start=now,
            parties=0,
            body="Hello, this is a test message",
            encoding=Encoding.NONE,
            mediatype="text/plain",
        )
    )
    vcon.sessions[0].parties = [0, 1]

    # Events replace the old party_history
    vcon.add_event(Event(type="join", time=now, sessions=0, party=0))

    vcon.add_analysis(
        Analysis(
            type="sentiment",
            vendor="example",
            dialog=0,
            body={"score": 0.8, "label": "positive"},
            encoding=Encoding.JSON,
        )
    )

    # Tags are scoped to the only Session unless dialog= or session= is given
    vcon.add_tag("category", "support")

    # A lawful basis attachment is never added for you
    print("Lawful basis present:", vcon.has_lawful_basis())

    is_valid, errors = vcon.is_valid()
    if not is_valid:
        for error in errors:
            print(f"- {error}")
        return

    json_str = vcon.to_json()
    print(json_str)

    loaded = VCon.build_from_json(json_str)
    print(f"Sessions: {len(loaded.sessions)}  Events: {len(loaded.events)}")
    print(f"Category tag: {loaded.get_tag('category')}")


if __name__ == "__main__":
    main()
