from django.db import models
from six import python_2_unicode_compatible

from eventtools.models import BaseEvent, BaseOccurrence


@python_2_unicode_compatible
class MyEvent(BaseEvent):
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title


class MyOccurrence(BaseOccurrence):
    event = models.ForeignKey(MyEvent, on_delete=models.CASCADE)


class MyOtherOccurrence(BaseOccurrence):
    event = models.ForeignKey(MyEvent, on_delete=models.CASCADE)
