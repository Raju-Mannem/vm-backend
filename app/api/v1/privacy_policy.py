from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/privacy-policy", response_class=HTMLResponse, tags=["Privacy"])
async def privacy_policy():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Privacy Policy</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 40px auto;
                padding: 20px;
                line-height: 1.7;
                color: #333;
            }
            h1, h2 {
                color: #111;
            }
            a {
                color: #0066cc;
            }
        </style>
    </head>
    <body>
        <h1>Privacy Policy</h1>
        <p>Last updated: May 2026</p>

        <p>
            This application uses WhatsApp and Meta platform services to communicate
            with users and provide automated messaging functionality.
        </p>

        <h2>Information We Collect</h2>
        <ul>
            <li>Name and phone number</li>
            <li>WhatsApp message content</li>
            <li>Technical logs and usage data</li>
        </ul>

        <h2>How We Use Information</h2>
        <p>
            We use the collected information to:
        </p>
        <ul>
            <li>Provide customer communication services</li>
            <li>Respond to inquiries</li>
            <li>Improve system reliability and security</li>
        </ul>

        <h2>Data Sharing</h2>
        <p>
            We do not sell personal information. Data may be processed through
            Meta and WhatsApp services as required for messaging functionality.
        </p>

        <h2>Data Security</h2>
        <p>
            We take reasonable security measures to protect user information.
        </p>

        <h2>Contact</h2>
        <p>
            If you have any questions about this Privacy Policy, contact us at:
            <br />
            <strong>raj@zeusit.us</strong>
        </p>

        <h2>Data Deletion Request</h2>
        <p>
            Users may request deletion of their data by contacting us through
            the email above.
        </p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)