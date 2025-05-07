"""
Basic usage example of pydantic-vcon
"""

from datetime import datetime
from pydantic_vcon import (
    VCon, Party, Dialog, DialogType, Encoding,
    Analysis, Attachment, CivicAddress
)

def main():
    # Create a new vCon
    vcon = VCon.build_new()
    
    # Add a party with contact information
    party = Party(
        tel="+1234567890",
        name="John Doe",
        civicaddress=CivicAddress(
            country="US",
            a1="CA",
            a3="San Francisco"
        )
    )
    vcon.add_party(party)
    
    # Add a text dialog
    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,  # Reference to the first party
        body="Hello, this is a test message",
        encoding=Encoding.JSON
    )
    vcon.add_dialog(dialog)
    
    # Add sentiment analysis
    analysis = Analysis(
        type="sentiment",
        vendor="example",
        body={"score": 0.8, "label": "positive"},
        encoding=Encoding.JSON
    )
    vcon.add_analysis(analysis)
    
    # Add a transcript attachment
    attachment = Attachment(
        type="transcript",
        body="This is a transcript of the conversation",
        encoding=Encoding.JSON
    )
    vcon.add_attachment(attachment)
    
    # Add some tags
    vcon.add_tag("category", "support")
    vcon.add_tag("priority", "high")
    
    # Validate the vCon
    is_valid, errors = vcon.is_valid()
    if not is_valid:
        print("Validation errors:")
        for error in errors:
            print(f"- {error}")
        return
    
    # Convert to JSON
    json_str = vcon.to_json()
    print("\nSerialized vCon:")
    print(json_str)
    
    # Load from JSON
    loaded_vcon = VCon.build_from_json(json_str)
    print("\nLoaded vCon:")
    print(f"UUID: {loaded_vcon.uuid}")
    print(f"Parties: {len(loaded_vcon.parties)}")
    print(f"Dialogs: {len(loaded_vcon.dialog)}")
    print(f"Analysis: {len(loaded_vcon.analysis)}")
    print(f"Attachments: {len(loaded_vcon.attachments)}")
    print(f"Category tag: {loaded_vcon.get_tag('category')}")
    print(f"Priority tag: {loaded_vcon.get_tag('priority')}")

if __name__ == "__main__":
    main() 