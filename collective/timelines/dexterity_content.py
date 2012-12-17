import xml.etree.ElementTree as ET
from zope.interface import alsoProvides
from zope.component import getMultiAdapter
from zope.schema import Bool, Datetime
from zope.traversing.interfaces import TraversalError
from DateTime import DateTime
from five import grok
from plone.directives import form
from plone.dexterity.interfaces import IDexterityContent
from collective.timelines.interfaces import ITimelineContent
from collective.timelines import timelinesMessageFactory as _, format_datetime


class ITimelineBehavior(form.Schema):
    """Add timeline configuration to content"""
    form.fieldset(
            'timeline',
            label=_(u'Timeline Config'),
            fields=('use_pub_date', 'timeline_date', 'timeline_end',
                    'bce_year', 'year_only'),
            )

    use_pub_date = Bool(title=_(u"Use Publication Date(s)"))

    timeline_date = Datetime(title=_(u"Custom Timeline Date"),
                             required=False)

    timeline_end = Datetime(title=_(u"Timeline End Date"),
                             required=False)

    bce_year = Bool(title = _(u'Year is BCE'), default=False)
    year_only = Bool(title = _(u'Show Year Only'), default=False)


alsoProvides(ITimelineBehavior, form.IFormFieldProvider)


class TimeLineContent(grok.Adapter):
    grok.provides(ITimelineContent)
    grok.context(IDexterityContent)

    def date(self):
        date = None
        context = self.context
        adapter = ITimelineBehavior(context, None)
        # Eventish items use the event start
        if hasattr(context, 'start_date'):
            date = context.start_date
        elif adapter and adapter.use_pub_date:
            # The DCFieldProperty is already a DateTime
            return self.context.effective_date
        elif adapter:
            date = adapter.timeline_date
        return date and DateTime(date.year, date.month, date.day,
                                 date.hour, date.minute)

    def end(self):
        date = None
        context = self.context
        adapter = ITimelineBehavior(context, None)
        # Eventish items use the event start
        if hasattr(context, 'end_date'):
            date = context.end_date
        elif adapter and adapter.use_pub_date:
            # The DCFieldProperty is already a DateTime
            return self.context.expiration_date
        elif adapter:
            date = adapter.timeline_end
        return date and DateTime(date.year, date.month, date.day,
                                 date.hour, date.minute)

    def _get_image_url(self):
        context = self.context
        # Look at the imaging view
        request = getattr(context, 'REQUEST', None)
        if request is not None:
            image_view = getMultiAdapter((context, request),
                                         name='images')
            try:
                image = image_view.traverse('image', ['preview'])
                if image:
                    # This returns an image tag, pull the src attribute
                    return ET.fromstring(image).attrib['src']
            except (AttributeError, TraversalError):
                pass

    def data(self, ignore_date=False):
        context = self.context
        bce = ITimelineBehavior(context).bce_year
        year_only = ITimelineBehavior(context).year_only
        data = {"headline": context.Title(),
                "text": "<p>%s</p>"%context.Description(),}

        if not ignore_date:
            date = self.date()
            if not date:
                return
            data['startDate'] = format_datetime(date, year_only)
            if bce:
                data['startDate'] = '-' + data['startDate']
            end = self.end()
            if end:
                data['endDate'] = format_datetime(end, year_only)
                if bce:
                    data['endDate'] = '-' + data['endDate']


        subject = context.Subject()
        if subject:
            # Take the first keyword, somewhat arbitrarily
            data['tag'] = subject[0]

        data['asset'] = {}
        # Links
        if hasattr(context, 'remoteUrl'):
            data['asset']['media'] = context.remoteUrl.encode('utf-8')
        elif not ignore_date:
            # Include a url to the content
            data['text'] = (data['text'] +
                    ' <a href="%s">more &hellip;</a>'%context.absolute_url())

        image_url = self._get_image_url()
        # Items with Images
        if image_url:
            data['asset']['thumbnail'] = image_url
            if 'media' not in data['asset']:
                data['asset']['media'] = image_url

        # News-like items
        if 'asset' in data and hasattr(context, 'image_caption'):
            data['asset']['caption'] = (
                context.image_caption.encode('utf-8')
                )
        # TODO: Asset 'credit'?

        return data
