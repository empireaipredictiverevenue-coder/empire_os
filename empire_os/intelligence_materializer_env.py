"""Canonical protected EmpireDB configuration for the dedicated materializer."""
from empire_os.runtime_env import load_runtime_env

KEY = 'EMPIRE_INTELLIGENCE_MATERIALIZER_DSN'
LOGIN = 'empire_intelligence_materializer_login'


def load_materializer_env() -> dict[str, str]:
    # Exported systemd environment takes precedence over protected host files.
    # Old runtime/secrets files may target the retired database; no fallback.
    env = load_runtime_env('/etc/empire_os.env')
    if not env.get(KEY):
        database_env = load_runtime_env('/etc/empiredb.env')
        if database_env.get(KEY):
            env[KEY] = database_env[KEY]
    dsn = env.get(KEY, '').strip()
    if not dsn:
        raise ValueError(KEY + ' is required')
    try:
        from psycopg.conninfo import conninfo_to_dict
        config = conninfo_to_dict(dsn)
    except Exception:
        raise ValueError('invalid dedicated materializer configuration') from None
    if config.get('user') != LOGIN or config.get('dbname') != 'empiredb':
        raise ValueError('dedicated EmpireDB materializer login/database required')
    if config.get('service') or config.get('options'):
        raise ValueError('materializer service/options overrides are not permitted')
    return {KEY: dsn}
