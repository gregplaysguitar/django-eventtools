from datetime import datetime, date, timedelta
from dateutil import rrule
from dateutil.relativedelta import relativedelta

from django.test import TestCase
from .models import Event, Occurrence


class EventToolsTestCase(TestCase):

    def setUp(self):
        self.christmas = Event.objects.create(title='Christmas')
        Occurrence.objects.create(
            event=self.christmas,
            start=datetime(2000, 12, 25, 7, 0),
            end=datetime(2000, 12, 25, 22, 0),
            repeat=rrule.YEARLY)

        self.weekends = Event.objects.create(title='Weekends 9-10am')
        # Saturday
        Occurrence.objects.create(
            event=self.weekends,
            start=datetime(2015, 1, 3, 9, 0),
            end=datetime(2015, 1, 3, 10, 0),
            repeat=rrule.WEEKLY)
        # Sunday
        Occurrence.objects.create(
            event=self.weekends,
            start=datetime(2015, 1, 4, 9, 0),
            end=datetime(2015, 1, 4, 10, 0),
            repeat=rrule.WEEKLY)

        self.daily = Event.objects.create(title='Daily 7-8am')
        Occurrence.objects.create(
            event=self.daily,
            start=datetime(2015, 1, 1, 7, 0),
            end=datetime(2015, 1, 1, 8, 0),
            repeat=rrule.DAILY)

        self.past = Event.objects.create(title='Past event')
        Occurrence.objects.create(
            event=self.past,
            start=datetime(2014, 1, 1, 7, 0),
            end=datetime(2014, 1, 1, 8, 0))

        self.future = Event.objects.create(title='Future event')
        Occurrence.objects.create(
            event=self.future,
            start=datetime(2016, 1, 1, 7, 0),
            end=datetime(2016, 1, 1, 8, 0))

        # fake "today" so tests always work
        self.today = date(2015, 6, 1)
        self.first_of_year = date(2015, 1, 1)
        self.last_of_year = date(2015, 12, 31)

    def test_single_occurrence(self):
        occ = self.christmas.occurrence_set.get()

        # using date() arguments
        dates = list(occ.all_occurrences(
            from_date=date(2015, 12, 1),
            to_date=date(2015, 12, 31),))
        self.assertEqual(len(dates), 1)

        # check it works as expected when from/to equal the occurrence date
        dates = list(occ.all_occurrences(
            from_date=date(2015, 12, 25),
            to_date=date(2015, 12, 25), ))
        self.assertEqual(len(dates), 1)

        # using datetime() arguments
        dates = list(occ.all_occurrences(
            from_date=datetime(2015, 12, 25, 6, 0, 0),
            to_date=datetime(2015, 12, 25, 23, 0, 0), ))
        self.assertEqual(len(dates), 1)

        dates = list(occ.all_occurrences(
            from_date=datetime(2015, 12, 25, 10, 0, 0),
            to_date=datetime(2015, 12, 25, 23, 0, 0), ))
        self.assertEqual(len(dates), 0)

        # check next_occurence method for non-repeating occurrences
        occ = self.past.occurrence_set.get() \
                  .next_occurrence(from_date=self.today)
        self.assertEqual(occ, None)

        occ = self.future.occurrence_set.get() \
                  .next_occurrence(from_date=self.today)
        self.assertEqual(occ[0], datetime(2016, 1, 1, 7, 0))

        # and for repeating
        occ = self.daily.occurrence_set.get() \
                  .next_occurrence(from_date=self.today)
        self.assertEqual(occ[0].date(), self.today)

    def test_occurrence_qs(self):
        events = [self.christmas, self.past, self.future]
        occs = Occurrence.objects.filter(event__in=events)

        # two christmases and the future event
        dates = list(occs.all_occurrences(
            from_date=date(2015, 1, 1),
            to_date=date(2016, 12, 31),))
        self.assertEqual(len(dates), 3)

        # one christmas and the past event
        dates = list(occs.all_occurrences(
            from_date=date(2014, 1, 1),
            to_date=date(2014, 12, 31),))
        self.assertEqual(len(dates), 2)

        # test queryset filtering
        qs = occs.for_period(from_date=date(2015, 1, 1), exact=True)
        self.assertEqual(qs.count(), 2)

        qs = occs.for_period(to_date=date(2010, 1, 1), exact=True)
        self.assertEqual(qs.get().event, self.christmas)

        qs = occs.for_period(from_date=date(2017, 1, 1),
                             to_date=date(2017, 12, 31),
                             exact=True)
        self.assertEqual(qs.get().event, self.christmas)

    def test_single_event(self):
        # one christmas per year
        for i in range(0, 10):
            count = len(list(self.christmas.all_occurrences(
                from_date=self.first_of_year + relativedelta(years=i),
                to_date=self.first_of_year + relativedelta(years=i + 1))))
            self.assertEqual(count, 1)

        # but none in the first half of the year
        count = len(list(self.christmas.all_occurrences(
            from_date=self.first_of_year + relativedelta(years=1),
            to_date=self.first_of_year + relativedelta(months=6))))
        self.assertEqual(count, 0)

        # check the daily event happens on some arbitrary dates
        for days in (10, 30, 50, 80, 100):
            from_date = self.first_of_year + timedelta(days)
            count = len(list(self.daily.all_occurrences(
                from_date=from_date,
                to_date=from_date
            )))
            self.assertEqual(count, 1)

        # check the the weekend event occurs as expected in a series of 2 day
        # periods
        for days in range(1, 50):
            from_date = self.first_of_year + timedelta(days)

            if from_date.weekday() == 5:
                expected = 2  # whole weekend
            elif from_date.weekday() in (4, 6):
                expected = 1  # one weekend day
            else:
                expected = 0  # no weekend days

            occs = list(self.weekends.all_occurrences(
                from_date=from_date,
                to_date=from_date + timedelta(1)
            ))
            self.assertEqual(len(occs), expected)

    def test_event_queryset(self):
        # one christmas per year
        christmas_qs = Event.objects.filter(pk=self.christmas.pk)
        for i in range(0, 10):
            occs = list(christmas_qs.all_occurrences(
                from_date=self.first_of_year + relativedelta(years=i),
                to_date=self.first_of_year + relativedelta(years=i + 1)))
            self.assertEqual(len(occs), 1)

        # but none in the first half of the year
        occs = list(christmas_qs.all_occurrences(
            from_date=self.first_of_year + relativedelta(years=1),
            to_date=self.first_of_year + relativedelta(months=6)))
        self.assertEqual(len(occs), 0)

        def sorted_events(events):
            return sorted(events, key=lambda obj: obj.pk)

        def expected(for_date):
            """Return ids of events expected to occur on a given date. """

            events = [self.daily]
            if for_date.month == 12 and for_date.day == 25:
                events.append(self.christmas)
            if for_date.weekday() in (5, 6):
                events.append(self.weekends)
            return sorted_events(events)

        # check the number of events for some arbitrary dates
        for days in (8, 16, 24, 32, 40, 48, 56):
            from_date = self.first_of_year + timedelta(days)
            qs = Event.objects.for_period(
                from_date=from_date,
                to_date=from_date,
                exact=True,
            ).distinct()

            events = sorted_events(list(qs))
            self.assertEqual(events, expected(from_date))

        # test queryset filtering
        events = Event.objects.filter(
            pk__in=(self.christmas.pk, self.future.pk, self.past.pk))

        qs = events.for_period(from_date=date(2015, 1, 1), exact=True)
        self.assertEqual(qs.count(), 2)

        qs = events.for_period(to_date=date(2010, 1, 1), exact=True)
        self.assertEqual(qs.get(), self.christmas)

        qs = events.for_period(from_date=date(2017, 1, 1),
                               to_date=date(2017, 12, 31),
                               exact=True)
        self.assertEqual(qs.get(), self.christmas)

    def test_occurrence_data(self):
        occ = self.christmas.occurrence_set.get()
        self.assertEqual(occ.next_occurrence()[2], occ.occurrence_data)
