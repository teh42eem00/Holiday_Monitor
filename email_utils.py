import yagmail


def send_email(subject, content, to_email):
    # Read the sender's email and password from the secrets file
    with open("static/secrets.txt", "r") as secrets_file:
        sender_email = secrets_file.readline().strip()
        sender_password = secrets_file.readline().strip()

    # Create a yagmail instance
    yag = yagmail.SMTP(sender_email, sender_password)

    # Send the email
    yag.send(to=to_email, subject=subject, contents=content)
