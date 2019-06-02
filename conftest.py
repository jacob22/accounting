import accounting.config
import pytransact.testsupport

def pytest_configure(config):
    global unconfigure
    unconfigure = pytransact.testsupport.use_unique_database()
    accounting.config.config.set('accounting', 'mongodb_dbname',
                                 pytransact.testsupport.dbname)


def pytest_unconfigure(config):
    unconfigure()
