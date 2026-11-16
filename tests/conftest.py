import os

os.environ['MONGO_MOCK_FOR_TESTS'] = '1'
os.environ['MONGODB_DATABASE'] = 'shopease_tests'
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
for key in (
    'GROQ_API_KEY',
    'SMTP_HOST',
    'SMTP_PORT',
    'SMTP_USERNAME',
    'SMTP_PASSWORD',
    'SMTP_FROM',
):
    os.environ.pop(key, None)

import pytest
import app as backend


@pytest.fixture(autouse=True)
def clear_test_database():
    for collection_name in backend.database.list_collection_names():
        backend.database[collection_name].delete_many({})
