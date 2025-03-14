﻿import re
import cudatext as ct

from cudax_lib import get_translation
_ = get_translation(__file__)  # i18n

from .setting import Setting
from .utils import get_indent, Parser, Date
from .utils import get_word_under_cursor
from .utils import TAGS  # to enable translations of @<tags> (Markus_F)

# from .dev import dbg
# dbg.disable()

MYLEXER = 'ToDo'
BREAKLINE = '＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿'
WORD_SEPS = '\t.,'
SNIPPETS = {
    'c': _('@critical'),
    'h': _('@high'),
    'l': _('@low'),
    't': _('@today'),
    's': TAGS.get('started') + '%d',
    'tg': TAGS.get('toggle') + '%d',
    'cr': TAGS.get('created') + '%d',
}


class Command:

    def __init__(self):
        self.cfg = Setting()
        self.parser = Parser()
        self.change_parser()
        self.date = Date()

        if MYLEXER not in ct.lexer_proc(ct.LEXER_GET_LEXERS, ''):
            ct.msg_box(_('Plugin "Plain Tasks" could not find its required lexer ToDo. Please install '
                         'this lexer from "Plugins / Addon Manager / Install" and restart CudaText.'),
                       ct.MB_OK+ct.MB_ICONERROR)

    def change_cfg(self):
        self.cfg.config()
        self.change_parser()

    def change_parser(self):
        def escape_re(s):
            for ch in r'\.[](){}*+-?':
                s = s.replace(ch, '\\'+ch)
            return s
        self.parser.re_item_bullet_open = re.compile(r'^\s*({})'.format(escape_re(self.cfg.task_bullet_open)))
        self.parser.re_item_bullet_done = re.compile(r'^\s*({})'.format(escape_re(self.cfg.task_bullet_done)))
        self.parser.re_item_bullet_cancel = re.compile(r'^\s*({})'.format(escape_re(self.cfg.task_bullet_cancel)))

    @staticmethod
    def get_selection_rows():
        carets = ct.ed.get_carets()
        x0, y0, x1, y1 = carets[0]
        if y1 < 0:
            return y0, y0
        if (y0, x0) > (y1, x1):
            x0, y0, x1, y1 = x1, y1, x0, y0
        if x1 == 0:
            y1 -= 1
        return y0, y1

    def make_tag_calc_time_for_task(self, line: str, iscomplete=True):
        if self.parser.has_tag_started(line):
            _started = self.parser.get_tag_started_date(line)
        else:
            _started = self.parser.get_tag_created_date(line)
        _date = self.date.calculate_time_for_task(_started,
                                                  self.parser.get_tag_toggle_dates(line),
                                                  self.cfg.date_format)
        if _date:
            return f"{TAGS.get('lasted') if iscomplete else TAGS.get('wasted')}{_date}"
        return ''

    def make_tag_with_date(self, tag):
        """Create @tag(date tznow)"""
        tag = tag if self.cfg.done_tag else ''
        date = self.date.datenow(self.cfg.date_format) if self.cfg.done_date else ''
        return ''.join([tag, date])

    @staticmethod
    def indent():
        if ct.ed.get_prop(ct.PROP_TAB_SPACES):
            return ct.ed.get_prop(ct.PROP_TAB_SIZE) * ' '
        else:
            return '\t'

    def offset(self, line: str) -> int:
        start_space = self.parser.get_start_space(line)
        tab_size = ' '*ct.ed.get_prop(ct.PROP_TAB_SIZE)
        return len(start_space.replace('\t', tab_size))

    def plain_tasks_new(self):

        lexname = ct.ed.get_prop(ct.PROP_LEXER_FILE)
        if lexname != MYLEXER:
            ct.file_open('')
            ct.ed.insert(0, 0, self.cfg.task_bullet_open+' ')
            ct.ed.set_caret(2, 0)
            ct.ed.set_prop(ct.PROP_LEXER_FILE, MYLEXER)
            return

        first, last = self.get_selection_rows()

        for n in range(first, last+1):
            line = ct.ed.get_text_line(n)
            indent = get_indent(line)
            if any([self.parser.isitem(line), self.parser.isheader(line), self.parser.isseparator(line)]):
                if n == last:
                    offset = ''
                    if self.parser.isheader(line) or self.parser.isseparator(line):
                        offset = self.indent()
                    if self.cfg.add_created_tag:
                        created_tag = self.cfg.space_before_tag + self.make_tag_with_date(_('@created'))
                    else:
                        created_tag = ''

                    new_line = ''.join([line[:indent],
                                        offset,
                                        self.cfg.task_bullet_open,
                                        ' ',
                                        created_tag
                                        ])
                    ct.ed.insert(len(line), n, '\n' + new_line)
                    ct.ed.set_caret(len(new_line)-len(created_tag), n+1)
            else:
                ct.ed.insert(indent, n, self.cfg.task_bullet_open+' ')
                if n == last:
                    ct.ed.set_caret(len(ct.ed.get_text_line(n)), n)

    def plain_tasks_complete(self):
        first, last = self.get_selection_rows()

        for n in range(first, last+1):
            line = ct.ed.get_text_line(n)
            line_init = line

            if self.parser.isseparator(line):
                pass

            elif self.parser.isitemdone(line):
                line = line.replace(self.cfg.task_bullet_done, self.cfg.task_bullet_open, 1)
                line = self.parser.del_tag_done(line)
                line = self.parser.del_tag_lasted(line)

            elif self.parser.isitemcancel(line):
                if self.parser.has_tag_wasted(line):
                    continue
                line = line.replace(self.cfg.task_bullet_cancel, self.cfg.task_bullet_done, 1)
                line = self.parser.del_tag_cancel(line)
                # add tag @done
                tag = self.make_tag_with_date(self.cfg.done_tag)
                if tag:
                    line += ''.join([self.cfg.space_before_tag, tag])

            elif self.parser.isitemopen(line):
                line = line.replace(self.cfg.task_bullet_open, self.cfg.task_bullet_done, 1)
                # add tag @done
                tag = self.make_tag_with_date(self.cfg.done_tag)
                if tag:
                    line += ''.join([self.cfg.space_before_tag, tag])
                # add tag @lasted
                if self.parser.has_tag_started(line) or self.parser.has_tag_created(line):
                    tag = self.make_tag_calc_time_for_task(line, True)
                    if tag:
                        line += ''.join([self.cfg.space_before_tag, tag])

            if line != line_init:
                ct.ed.set_text_line(n, line)

    # @dbg.snoop()
    def plain_tasks_cancel(self):
        first, last = self.get_selection_rows()

        for n in range(first, last+1):
            line = ct.ed.get_text_line(n)
            if self.parser.isseparator(line):
                pass

            elif self.parser.isitemcancel(line):
                line = line.replace(self.cfg.task_bullet_cancel, self.cfg.task_bullet_open, 1)
                # del tag @canceled
                line = self.parser.del_tag_wasted(line)
                line = self.parser.del_tag_cancel(line)

            elif self.parser.isitemdone(line):
                if self.parser.has_tag_lasted(line):
                    continue
                line = line.replace(self.cfg.task_bullet_done, self.cfg.task_bullet_cancel, 1)
                # del tag @done
                line = self.parser.del_tag_done(line)
                # add tag @canceled
                tag = self.make_tag_with_date(self.cfg.cancel_tag)
                if tag:
                    line += ''.join([self.cfg.space_before_tag, tag])

            elif self.parser.isitemopen(line):
                line = line.replace(self.cfg.task_bullet_open, self.cfg.task_bullet_cancel, 1)
                # add tag @canceled
                tag = self.make_tag_with_date(self.cfg.cancel_tag)
                if tag:
                    line += ''.join([self.cfg.space_before_tag, tag])
                # add tag @wasted
                if self.parser.has_tag_started(line) or self.parser.has_tag_created(line):
                    tag = self.make_tag_calc_time_for_task(line, False)
                    if tag:
                        line += ''.join([self.cfg.space_before_tag, tag])

            ct.ed.set_text_line(n, line)

    # @dbg.snoop()
    def plain_tasks_archive(self):
        alltext = ct.ed.get_text_all().split('\n')
        archivepos = len(alltext) - 1

        for n, t in enumerate(alltext):
            if t == BREAKLINE:
                _n = n + 1
                if _n <= archivepos and alltext[_n] == self.cfg.archive_name:
                    archivepos = _n
                    break
        else:
            ct.ed.set_text_line(-1, '')
            ct.ed.set_text_line(-1, BREAKLINE)
            ct.ed.set_text_line(-1, self.cfg.archive_name)
            archivepos += 3
        x = len(self.cfg.archive_name)

        def get_project(n):
            line = ct.ed.get_text_line(n)
            level = self.offset(line)
            if level == 0:
                return ''

            project = []
            while level > 0 and n > 0:
                n -= 1
                line = ct.ed.get_text_line(n)
                if self.parser.isheader(line):
                    lv = self.offset(line)
                    if lv < level:
                        project.append((self.parser.get_header(line), lv))
                        level = lv
            project.sort(key=lambda k: k[1])
            return _('@project({})').format(' / '.join([p[0] for p in project]))

        first, last = self.get_selection_rows()
        to_move = []
        for n in range(min(first, archivepos), min(last+1, archivepos)):
            line = ct.ed.get_text_line(n)

            if self.parser.isseparator(line):
                pass

            elif self.parser.isitemcancel(line) or self.parser.isitemdone(line):
                to_move.append((n, 1))
                line_indent = get_indent(line)
                while n < archivepos + 1:
                    n += 1
                    line = ct.ed.get_text_line(n)
                    if self.parser.issimpletext(line) and get_indent(line) > line_indent:
                        to_move.append((n, get_indent(line)-line_indent))
                    else:
                        break

        to_move.reverse()
        for md, offset in to_move:
            project = get_project(md)
            line = ct.ed.get_text_line(md).strip()
            t = ''.join(['\n', self.indent()*offset, line, self.cfg.space_before_tag, project])
            ct.ed.insert(x, archivepos, t)
        for rm, ___ in to_move:
            ct.ed.delete(0, rm, 0, rm+1)

    # @dbg.snoop()
    def on_key(self, ed_self, code, state):
        """Insert args for function under cursor"""
        if code == 9 and state == '':
            x0, y0, ___, y1 = ct.ed.get_carets()[0]
            if not any([y0 == y1, y1 == -1]):
                return
            line = ct.ed.get_text_line(y0)

            if self.parser.isseparator(line) or self.parser.isheader(line):
                pass
            elif self.parser.isitem(line):
                word, pos = get_word_under_cursor(line, x0, seps=WORD_SEPS)
                if word in SNIPPETS.keys():
                    date = self.date.datenow(self.cfg.date_format) if self.cfg.done_date else ''
                    snip = SNIPPETS[word].replace('%d', date)
                    ct.ed.replace(pos[0], y0, pos[1], y0, snip)
                    ct.ed.set_caret(pos[0]+len(snip), y0)
                    return False
