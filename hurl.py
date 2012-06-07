from django.core.urlresolvers import RegexURLPattern
from django.core.exceptions import ImproperlyConfigured

class Hurl(object):
    default_matcher = 'slug'
    DEFAULT_MATCHERS = {
        'int': r'\d+',
        'slug': r'[\w-]+'
    }

    def __init__(self, name_prefix=''):
        self.name_prefix = name_prefix
        self.matchers = dict(self.DEFAULT_MATCHERS)

    def urlpatterns(self, prefix, pattern_dict):
        patterns = self.patterns(prefix, pattern_dict)
        urlpatterns = []
        for p in patterns:
            urlpatterns.append(RegexURLPattern(*p))
        return urlpatterns

    def patterns(self, prefix, pattern_dict):
        urls = self.patterns_recursive(pattern_dict)
        urls = self.add_prefix_suffix(urls)
        if prefix:
            urls = self.add_views_prefix(prefix, urls)
        urls = self.add_names(urls)
        return urls

    def patterns_recursive(self, pattern_dict):
        urls = []
        for url, view in pattern_dict.items():
            re_str = self.make_re_str(url)
            if isinstance(view, dict):
                re_list = self.patterns_recursive(view)
                for pattern, view_name in re_list:
                    if pattern == '':
                        urls.append((re_str, view_name))
                    else:
                        urls.append((re_str + '/' + pattern, view_name))
            else:
                urls.append((re_str, view))
        return urls

    def add_prefix_suffix(self, urls):
        formatted_urls = []
        for url, view in urls:
            if url != '':
                url = '^{url}/$'.format(url=url)
            else:
                url = '^$'
            formatted_urls.append((url, view))
        return formatted_urls

    def add_views_prefix(self, prefix, urls):
        new_urls = []
        for url, view in urls:
            if isinstance(view, basestring):
                full_view_name = '.'.join((prefix, view))
            else:
                full_view_name = view
            new_urls.append((url, full_view_name))
        return new_urls

    def make_re_str(self, url):
        parts = []
        s = ''
        for c in url:
            if c == '<':
                parts.append(s)
                s = ''
            elif c == '>':
                parts.append(self.transform(s))
                s = ''
            else:
                s += c
        parts.append(s)
        return '{0}'.format(''.join(parts))

    def transform(self, pattern):
        parts = pattern.split(':')
        if len(parts) == 1:
            name = parts[0]
            type = name
        elif len(parts) == 2:
            name, type = parts
        else:
            raise StandardError('Fix')
        matcher = self.generate_matcher(type)
        if name:
            return r'(?P<{name}>{matcher})'.format(name=name, matcher=matcher)
        else:
            return r'({matcher})'.format(matcher=matcher)


    def generate_matcher(self, type):
        try:
            return self.matchers[type]
        except KeyError:
            return self.matchers[self.default_matcher]

    def add_names(self, urls):
        new_urls = []
        for url, view in urls:
            if isinstance(view, basestring):
                name = view.split('.')[-1]
                if self.name_prefix:
                    name = '{prefix}_{name}'.format(prefix=self.name_prefix, name=name)
                new_urls.append((url, view, {}, name))
            elif callable(view):
                name = getattr(view, 'func_name')
                if name:
                    if self.name_prefix:
                        name = '{prefix}_{name}'.format(prefix=self.name_prefix, name=name)
                    new_urls.append((url, view, {}, name))
                else:
                    new_urls.append((url, view))
            else:
                new_urls.append((url, view))
        return new_urls


def urlpatterns( prefix, pattern_dict):
    h = Hurl()
    return h.urlpatterns(prefix, pattern_dict)

class Parser(object):

    def parse(self, input_url):
        result = []
        parts = input_url.split('/')
        for part in parts:
            result.extend(self.parse_part(part))
        return result

    def parse_part(self, input_url):
        parts = []

        text_part = ""
        started_parameter = False

        for character in input_url:
            if character == ' ':
                if started_parameter and text_part:
                    text_part += character
                continue
            elif character == '<':
                if started_parameter:
                    raise ImproperlyConfigured("Missing '>'.")
                started_parameter = True
                if text_part:
                    parts.append(StaticPart(text_part))
                    text_part = ''
            elif character == '>':
                if not started_parameter:
                    raise ImproperlyConfigured("Missing '<'.")
                started_parameter = False
                parts.append(self.parse_param(text_part))
                text_part = ""
            else:
                text_part += character
        if started_parameter:
            raise ImproperlyConfigured("Missing '>'.")
        if text_part.strip() != '':
            parts.append(StaticPart(text_part))
        return parts

    def parse_param(self, param):
        name_type = [part.strip() for part in param.split(':')]
        if len(name_type) == 0:
            raise ImproperlyConfigured("Bad parameter")
        elif len(name_type) == 1:
            name = name_type[0].strip()
            type = None
        elif len(name_type) == 2:
            name, type = name_type
        else:
            raise ImproperlyConfigured("Cannot use more than one colon in parameter.")

        if name and len(name.strip().split(" ")) > 1:
            raise ImproperlyConfigured("Name of parameter cannot contain spaces.")

        if type and len(type.strip().split(" ")) > 1:
            raise ImproperlyConfigured("Type of parameter cannot contain spaces.")

        return PatternPart(name, type)

class StaticPart(object):
    def __init__(self, pattern):
        self.pattern = pattern

    def __eq__(self, other):
        if type(self) == type(other):
            return self.pattern == other.pattern
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class PatternPart(object):
    def __init__(self, name='', type=None):
        if name == '' and type is None:
            raise TypeError('Either name or type required')
        self.name = name
        self.type = type or name

    def __eq__(self, other):
        if type(self) == type(other):
            return self.name == other.name and \
                   self.type == other.type
        return False

    def __ne__(self, other):
        return not self.__eq__(other)
