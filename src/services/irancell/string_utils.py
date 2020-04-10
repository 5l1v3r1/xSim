import re
from src.models.enums import IrancellServiceType
from src.models.offer import Offer


def detect_start_and_end_hours(string_fa):
    am_indexes = [{'type': 'AM', 'index': am.start()} for am in re.finditer('صبح', string_fa)]
    pm_indexes = [{'type': 'PM', 'index': pm.start()} for pm in re.finditer('ظهر', string_fa)]

    am_pm_indexes = sorted(am_indexes + pm_indexes, key=lambda string_fa: string_fa['index'])
    assert 0 < len(am_pm_indexes) < 3

    if len(am_pm_indexes) == 1:
        first_am_pm = second_am_pm = am_pm_indexes[0]['type']
    else:
        first_am_pm, second_am_pm = am_pm_indexes[0]['type'], am_pm_indexes[1]['type']

    first_hour, second_hour = list(map(int, re.findall(r'\d+', string_fa)))

    result = [{'hour': first_hour, 'type': first_am_pm}, {'hour': second_hour, 'type': second_am_pm}]

    remaining = string_fa.replace(str(result[0]['hour']), '') \
        .replace(str(result[1]['hour']), '') \
        .replace('صبح', '') \
        .replace('ظهر', '') \
        .replace(')', '') \
        .replace('(', '') \
        .replace('تا', '')

    return result, remaining


def detect_limitation_hours(string_fa):
    ta_index = string_fa.find('تا')
    if ta_index == -1:
        return None, string_fa

    lp_index = string_fa.find('(') if string_fa.find('(') >= 0 else 0
    rp_index = string_fa.find(')') if string_fa.find(')') >= 0 else len(string_fa)

    left, right = max(ta_index - 9, lp_index), min(ta_index + 9, rp_index + 1)
    point_of_interest = string_fa[left:right]

    result, remaining = detect_start_and_end_hours(point_of_interest)

    return result, string_fa[:left] + remaining + string_fa[right:]


def detect_number(string_fa):
    fa_string_numbers = ['صفر', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
    fa_numeric_numbers = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']

    result, string, remaining = None, '', string_fa
    for i, (string_number, numeric_number) in \
            enumerate(zip(fa_numeric_numbers, fa_string_numbers)):
        if string_number in string_fa:
            assert result == None
            result, string, remaining = i, string_number, string_fa.replace(string_number, '')
        if numeric_number in string_fa:
            assert result == None
            result, string, remaining = i, numeric_number, string_fa.replace(numeric_number, '')

    if re.findall(r'\d+', string_fa):
        assert result == None
        number = int(re.findall(r'\d+', string_fa)[0])
        result, string, remaining = number, str(number), string_fa.replace(str(number), '')

    return result, string, remaining


def detect_duration(string_fa):
    keywords = {
        'daily': 'روزانه',
        'weekly': 'هفتگی',
        'hour': 'ساعته',
        'day': 'روزه',
    }

    if keywords['daily'] in string_fa:
        return 24, string_fa.replace(keywords['daily'], '')

    elif keywords['weekly'] in string_fa:
        return 7 * 24, string_fa.replace(keywords['weekly'], '')

    elif keywords['hour'] in string_fa or keywords['day'] in string_fa:
        keyword = keywords['hour'] if keywords['hour'] in string_fa else keywords['day']
        keyword_index = string_fa.find(keyword)

        point_of_interest = string_fa[max(0, keyword_index - 5):keyword_index + len(keyword)]

        result, number_string, remaining = detect_number(point_of_interest)

        point_of_interest_remaining = point_of_interest.replace(number_string, '').replace(keyword, '')

        remaining = string_fa[:max(0, keyword_index - 5)] \
                    + point_of_interest_remaining \
                    + string_fa[keyword_index + len(keyword):]

        keyword_value = 1 if keyword == keywords['hour'] else 24
        return keyword_value * result, remaining

    return None, string_fa


def detect_service_type(string_fa):
    if 'چارخونه' in string_fa:
        remaining = string_fa.replace('چارخونه', '')
        return IrancellServiceType.CHARKHONE, remaining
    elif 'داخلی' in string_fa:
        remaining = string_fa.replace('داخلی', '')
        return IrancellServiceType.LOCAL, remaining
    else:
        remaining = string_fa.replace('بین‌الملل', '')
        return IrancellServiceType.INTERNATIONAL, remaining


def detect_offer_size_and_type(string_fa):
    service_type, remaining = detect_service_type(string_fa)

    value = None
    if service_type == IrancellServiceType.CHARKHONE:
        assert 'تومان' in remaining
        value = int(re.findall(r'\d+', remaining)[0])
    else:
        if 'مگ' in remaining or 'گیگ' in remaining:
            value = float(re.findall(r'\d+\.*\d*', remaining)[0]) * (1024 if 'گیگ' in remaining else 1)

    return {'type': service_type, 'value': value}


def detect_offer_by_name(string_fa):
    new_offer = Offer(fa_name=string_fa)

    duration, remaining = detect_duration(string_fa)
    new_offer.set_duration(duration)

    limitation_hours, remaining = detect_limitation_hours(remaining)

    if ' با' in remaining:
        ba_index = remaining.find(' با')
        first, second = remaining[:ba_index], remaining[ba_index + 3:]

        first_size = detect_offer_size_and_type(first)
        second_size = detect_offer_size_and_type(second)

        if first_size['type'] == second_size['type']:
            new_offer.add_value(first_size['type'], first_size['value'])
            new_offer.add_value(second_size['type'], second_size['value'], limitation_hours)
        else:
            new_offer.add_value(first_size['type'], first_size['value'], limitation_hours)
            new_offer.add_value(second_size['type'], second_size['value'], limitation_hours)
    else:
        size = detect_offer_size_and_type(remaining)
        new_offer.add_value(size['type'], size['value'], limitation_hours)

    return new_offer