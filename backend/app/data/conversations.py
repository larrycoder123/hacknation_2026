"""Mock conversation and message data."""

from ..schemas.conversations import Conversation
from ..schemas.messages import Message

MOCK_CONVERSATIONS: dict[str, Conversation] = {
    "1024": Conversation(
        id="1024",
        customer_name="Alice Johnson",
        subject="Cannot access property certifications",
        priority="High",
        status="Open",
        time_ago="5m",
        last_message="I am getting Error 505 when trying to view certificates.",
    ),
    "1025": Conversation(
        id="1025",
        customer_name="Bob Smith",
        subject="Billing question for March",
        priority="Medium",
        status="Open",
        time_ago="12m",
        last_message="Why was I charged twice?",
    ),
    "1026": Conversation(
        id="1026",
        customer_name="Charlie Brown",
        subject="Feature request: Dark mode",
        priority="Low",
        status="Pending",
        time_ago="1h",
        last_message="Any updates on dark mode support?",
    ),
    "1027": Conversation(
        id="1027",
        customer_name="Diana Prince",
        subject="Login issues on mobile",
        priority="High",
        status="Open",
        time_ago="2h",
        last_message="The app crashes when I try to log in.",
    ),
    "1028": Conversation(
        id="1028",
        customer_name="Evan Wright",
        subject="Where can I find the API key?",
        priority="Medium",
        status="Resolved",
        time_ago="1d",
        last_message="Found it, thanks!",
    ),
    "1029": Conversation(
        id="1029",
        customer_name="Marcus Chen",
        subject="Facilities tile missing from home page",
        priority="Medium",
        status="Open",
        time_ago="3d",
        last_message="Cache clear fixed it, thanks!",
    ),
}

MOCK_MESSAGES: dict[str, list[Message]] = {
    "1024": [
        Message(
            id="m1",
            conversation_id="1024",
            sender="customer",
            content="Hi, I am trying to access the property certifications for my new listing, but I keep getting an Error 505 page.",
            timestamp="10:30 AM",
        ),
        Message(
            id="m2",
            conversation_id="1024",
            sender="agent",
            content="Hello Alice, I can help you with that. Let me check your account details.",
            timestamp="10:32 AM",
        ),
        Message(
            id="m3",
            conversation_id="1024",
            sender="customer",
            content="Okay, thanks. It is for property ID prop-8821.",
            timestamp="10:33 AM",
        ),
    ],
    "1025": [
        Message(
            id="m4",
            conversation_id="1025",
            sender="customer",
            content="I see two charges for March on my statement. Can you explain?",
            timestamp="10:15 AM",
        ),
        Message(
            id="m5",
            conversation_id="1025",
            sender="agent",
            content="Hi Bob, I'd be happy to look into this for you. Could you provide the last 4 digits of the card used?",
            timestamp="10:18 AM",
        ),
        Message(
            id="m6",
            conversation_id="1025",
            sender="customer",
            content="Sure, it ends in 4521.",
            timestamp="10:20 AM",
        ),
    ],
    "1026": [
        Message(
            id="m7",
            conversation_id="1026",
            sender="customer",
            content="Hey, I was wondering if you have any plans to add dark mode? It would be really helpful for late night work.",
            timestamp="09:00 AM",
        ),
        Message(
            id="m8",
            conversation_id="1026",
            sender="agent",
            content="Hi Charlie! Thanks for the suggestion. Dark mode is on our roadmap for Q2 this year.",
            timestamp="09:15 AM",
        ),
        Message(
            id="m9",
            conversation_id="1026",
            sender="customer",
            content="Any updates on dark mode support?",
            timestamp="10:00 AM",
        ),
    ],
    "1027": [
        Message(
            id="m10",
            conversation_id="1027",
            sender="customer",
            content="The app crashes when I try to log in on my iPhone. It worked fine yesterday.",
            timestamp="08:30 AM",
        ),
        Message(
            id="m11",
            conversation_id="1027",
            sender="agent",
            content="Sorry to hear that, Diana. What iOS version are you running?",
            timestamp="08:35 AM",
        ),
        Message(
            id="m12",
            conversation_id="1027",
            sender="customer",
            content="iOS 17.3.",
            timestamp="08:36 AM",
        ),
        Message(
            id="m13",
            conversation_id="1027",
            sender="agent",
            content="Thank you. We've identified an issue with the latest app update on iOS 17.3. Our team is working on a fix. In the meantime, try force-closing the app and logging in again.",
            timestamp="08:40 AM",
        ),
    ],
    "1028": [
        Message(
            id="m14",
            conversation_id="1028",
            sender="customer",
            content="Where can I find my API key for the developer dashboard?",
            timestamp="Yesterday 2:00 PM",
        ),
        Message(
            id="m15",
            conversation_id="1028",
            sender="agent",
            content="Hi Evan! You can find your API key in Settings > Developer > API Keys. Let me know if you need further help!",
            timestamp="Yesterday 2:05 PM",
        ),
        Message(
            id="m16",
            conversation_id="1028",
            sender="customer",
            content="Found it, thanks!",
            timestamp="Yesterday 2:10 PM",
        ),
    ],
    "1029": [
        Message(
            id="m17",
            conversation_id="1029",
            sender="customer",
            content="Hi, I cannot find the Facilities tile on my Unified Platform home page. I have PropertySuite access but Facilities is not showing up.",
            timestamp="Monday 9:15 AM",
        ),
        Message(
            id="m18",
            conversation_id="1029",
            sender="agent",
            content="Hi Marcus! The Facilities tile is actually built into PropertySuite - it's not a separate tile. Since you have PropertySuite access, Facilities should be available automatically inside the PropertySuite menu. No additional roles or permissions are needed. Try clearing your browser cache and refreshing - that usually fixes this display issue.",
            timestamp="Monday 9:20 AM",
        ),
        Message(
            id="m19",
            conversation_id="1029",
            sender="customer",
            content="Cache clear fixed it, thanks!",
            timestamp="Monday 9:35 AM",
        ),
    ],
}

