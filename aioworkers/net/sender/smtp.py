import smtplib
from email.mime.text import MIMEText
from typing import Optional, Sequence

from aioworkers.core.base import ExecutorEntity, LoggingEntity
from aioworkers.net.sender import AbstractSender


class SMTP(ExecutorEntity, LoggingEntity, AbstractSender):
    _conn = None  # type: Optional[smtplib.SMTP]

    def set_config(self, config):
        config = config.new_child({self.PARAM_EXECUTOR: 1})
        super().set_config(config)

    def set_context(self, context):
        super().set_context(context)
        context.on_disconnect.append(self.disconnect)

    async def send_message(self, msg):
        await self.connect()
        m = MIMEText(msg['body'])
        mail_to = msg['to']
        if isinstance(mail_to, str):
            pass
        elif isinstance(mail_to, Sequence):
            mail_to = ', '.join(mail_to)
        m['To'] = mail_to
        m['Subject'] = msg['subject']
        m['From'] = msg.get('from') or self.config.get('from')
        self.logger.debug('Send message: %s', msg['subject'])
        return await self.run_in_executor(self._conn.send_message, m)

    def _connect(self):
        if self._conn is not None:
            code, _ = self._conn.noop()
            if code == 250:
                return
            else:
                self._conn.close()
                self._conn = None
        host = self.config.get('host', 'localhost')
        port = self.config.get_int('port', 0)
        self.logger.info('Connect to %s', host)
        if self.config.get('ssl'):
            conn = smtplib.SMTP_SSL(host, port)
        else:
            conn = smtplib.SMTP(host, port)
        if self.config.get('tls'):
            conn.ehlo()
            conn.starttls()

        login = self.config.get('login')
        if login:
            self.logger.info('Login with %s', login)
            conn.login(login, self.config.get('password'))
        self._conn = conn

    async def connect(self):
        await self.run_in_executor(self._connect)

    async def disconnect(self):
        if self._conn is not None:
            await self.run_in_executor(self._conn.close)
            self._conn = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
