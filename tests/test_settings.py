
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME':  'test.sqlite',
    }
}

SECRET_KEY = '1'

INSTALLED_APPS = [
    "tests",
]
