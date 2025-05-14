import ssl
import certifi
from django.core.mail.backends.smtp import EmailBackend

class CertifiEmailBackend(EmailBackend):
    def open(self):
        if self.connection:
            return False
        connection_params = (self.host, self.port)
        self.connection = self.connection_class(*connection_params, timeout=self.timeout)

        # Fix the _debug attribute error
        self.connection.set_debuglevel(getattr(self, '_debug', False))

        if self.use_tls:
            certifi_context = ssl.create_default_context(cafile=certifi.where())
            self.connection.starttls(context=certifi_context)

        if self.username and self.password:
            self.connection.login(self.username, self.password)

        return True
