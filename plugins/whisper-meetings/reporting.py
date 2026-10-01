"""Readable reports; evidence remains internal structured metadata."""
import copy
import re


def clean(text):
    # Remove legacy inline source lists/links without stripping ordinary numbers.
    text = re.sub(r'\[(?:s\d{5}(?:\s*[,;]\s*|\s+)?)+\](?:\([^)]*\))?', '', text)
    text = re.sub(r'\bs\d{5}\b', '', text)
    return re.sub(r'[ \t]+', ' ', text).replace(' .', '.').strip()


def view(analysis):
    result = copy.deepcopy(analysis)
    summary = clean(result['summary'])
    sections = result.get('overview') or []
    if not sections and len(summary) > 500:
        # Existing reports: preserve every sentence, without inventing headings.
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9])', summary)
        summary = ' '.join(sentences[:2])
        sections = [{'title': 'Подробности' if re.search('[А-Яа-я]', summary) else 'Details',
                     'points': sentences[2:]}] if len(sentences) > 2 else []
    result['summary'] = summary
    result['overview'] = [{'title': clean(section['title']), 'points': [clean(point) for point in section['points']]}
                          for section in sections]
    for key in ('decisions', 'action_items', 'risks', 'open_questions'):
        for entry in result[key]:
            entry['text'] = clean(entry['text'])
    return result


def introduction(analysis, heading='Кратко'):
    report = view(analysis)
    lines = [f'## {heading}', '', report['summary'], '']
    for section in report['overview']:
        lines += [f"### {section['title']}", '']
        lines += [f'- {point}' for point in section['points']]
        lines.append('')
    return lines
