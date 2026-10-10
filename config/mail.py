"""The store's development email backend."""

from django.core.mail.backends import console


class ConsoleEmailBackend(console.EmailBackend):
    """Print each email as it was written, not as it travels.

    Django's console backend prints the encoded message, which breaks any
    line over 78 characters in two with a trailing ``=``. A password reset
    link is longer than that, and it has to be copied out of the terminal
    whole.
    """

    def write_message(self, message):
        self.stream.write(f"Subject: {message.subject}\n")
        self.stream.write(f"From: {message.from_email}\n")
        self.stream.write(f"To: {', '.join(message.to)}\n\n")
        self.stream.write(f"{message.body}\n")
        self.stream.write("-" * 79)
        self.stream.write("\n")
