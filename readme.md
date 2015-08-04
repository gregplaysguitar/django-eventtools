# Example

    # myapp/models.py

    from django.db import models

    from eventtools.models import BaseEvent, BaseOccurrence


    class Event(BaseEvent):
        title = models.CharField(max_length=100)
        description = models.TextField()


    class Occurrence(BaseOccurrence):
        event = models.ForeignKey(Event)


## Usage        
    
    >>> from myapp.models import Event
     
    
    
## Occurrence data
