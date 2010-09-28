# -*- coding: utf-8 -*-
# Copyright (C) 2010  Wil Mahan <wmahan+fatics@gmail.com>
#
# This file is part of FatICS.
#
# FatICS is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FatICS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with FatICS.  If not, see <http://www.gnu.org/licenses/>.
#

import time
import re

import speed_variant
import online
import game

from match import MatchStringParser, MatchError
from game_constants import *

# Wait 90 seconds after a seek ends to reuse its seek number
# (this is the value GICS uses; original FICS is likely the
# same or similar)
EXPIRE_DELAY = 90

""" Max number of seeks per user. """
LIMIT = 3


seeks = {}

def find_free_slot():
    """ Find the first available seek number. """
    # This is O(n) in the number of games, but it's simple and should
    # be more than efficient enough.
    i = 1
    expiration_time = time.time() - EXPIRE_DELAY
    while True:
        if i not in seeks or (seeks[i].expired
                and seeks[i].expired_time <= expiration_time):
            return i
        i += 1

def find_matching(seek):
    """ Find all seeks that match a given seek.  Returns a list of
    matching auto seeks and a list of matching manual seeks. """
    # TODO: stop the search on a match for non-manual seeks?
    # Would that lead to starvation of seeks with a high number?
    auto_matches = []
    manual_matches = []
    for s in seeks.values():
        if seek.matches(s):
            if s.manual:
                manual_matches.append(s)
            else:
                auto_matches.append(s)
    auto_matches.sort(key=lambda s: s.when_posted)
    return (auto_matches, manual_matches)

class Seek(MatchStringParser):
    def __init__(self, user, args):
        """ Create a new seek.  Raises a MatchError if given an invalid
        match string. """
        self.a = user
        self.manual = None
        self.expired = False

        # may raise MatchError
        self._parse_args(args)

        assert(self.time is not None and self.inc is not None)
        assert(self.rated is not None)
        assert(self.variant_name is not None)
        assert(self.clock_name is not None)
        assert(self.side in [None, WHITE, BLACK])

        self.tags = {
            'time': self.time,
            'inc': self.inc,
            'rated': self.rated,
            'variant_name': self.variant_name,
            'clock_name': self.clock_name
        }

        # defaults
        if self.manual is None:
            self.manual = False
        if self.clock_name is None:
            self.clock_name = 'fischer'
        assert(self.manual in [True, False])

        self.speed_variant = speed_variant.from_names(self.speed_name,
            self.variant_name)

        name = self.a.get_display_name()
        speed_name = self.speed_variant.speed.name
        variant_str = '' if self.variant_name == 'chess' else (
            ' %s' % self.variant_name)
        clock_str = '' if self.clock_name == 'fischer' else (
            ' %s' % self.clock_name)

    def _parse_args(self, args):
        """ Parse the args, including seek-specific parsing. """
        self._parse_args_common(args, self.a)

        # seek-specific (not used in the match command)
        if self.rated is None:
            if self.a.is_guest or self.clock_name in [
                    'hourglass', 'untimed']:
                self.a.write(_('Setting seek to unrated.\n'))
                self.rated = False
            else:
                # Original FICS uses the 'rated' var, but we default to True
                self.rated = True
        elif self.rated and self.a.is_guest:
            raise MatchError(_('Only registered players can play rated games.\n'))

        self.rating = self.a.get_rating(self.speed_variant)

    def __eq__(self, other):
        """ Determine whether two seeks are exactly the same (same poster
        and parameters). """
        # ignore "manual" and "side" for comparison purposes
        return (self.expired == other.expired and
            self.a == other.a and self.tags == other.tags)

    def matches(self, other):
        """ Determine whether this seek matches another. """
        if other.expired:
            return False

        if self.a == other.a:
            # can't match own seek
            return False

        # side is a special case because it should be opposite
        if self.side is not None or other.side is not None:
            if self.side is None or other.side is None:
                return False
            if other.side == self.side:
                return False

        # easy!
        return self.tags == other.tags

    def post(self):
        """ Add this seek to the seek list.  Returns the number of users
        notified of the seek. """
        assert(not self.expired)

        self.when_posted = time.time()
        self.num = find_free_slot()
        seeks[self.num] = self
        self.a.session.seeks.append(self)

        # build the seek string
        name = self.a.get_display_name()
        rated_str = 'rated' if self.tags['rated'] else 'unrated'
        speed_name = self.speed_variant.speed.name
        variant_str = '' if self.variant_name == 'chess' else (
            ' %s' % self.variant_name)
        clock_str = '' if self.clock_name == 'fischer' else (
            ' %s' % self.clock_name)
        if self.side is None:
            side_str = ''
        else:
            side_str = ' [white]' if self.side == WHITE else ' [black]'

        # not currently translated, for efficiency
        seek_str = '%s (%s) seeking %d %d %s %s%s%s%s ("play %d" to respond)\n' % (
                name, self.rating, self.tags['time'], self.tags['inc'],
                rated_str, speed_name, variant_str, clock_str,
                side_str, self.num)

        count = 0
        for u in online.online:
            if u.vars['seek'] and not u.session.game:
                # showownseek is both a variable and an ivariable
                if u == self.a and not (u.vars['showownseek']
                        and u.session.ivars['showownseek']):
                    continue
                # if either player censors or noplays the other, don't
                # notify of the seek
                if (self.a.name in u.censor or self.a.name in u.noplay
                        or u.name in self.a.censor or u.name in self.a.noplay):
                    continue
                # TODO: check formula for both players
                count += 1
                u.write(seek_str)

        # set the string for use in the "sought" display
        self._str = '%3d %4s %-17s %3d %3d %s %s%s%s%s\n' % (
            self.num, self.rating, name, self.time, self.inc,
            rated_str, speed_name, variant_str, clock_str,
            side_str)

        return count

    def met_by(self, b):
        """ Check whether the user B meets the requirements for accepting
        this seek. """
        return True

    def accept(self, b):
        assert(self.met_by(b))
        assert(not self.expired)
        self.b = b
        # will remove this seek
        game.PlayedGame(self)
        assert(self.expired)

    def remove(self):
        assert(seeks[self.num] == self)
        self.expired = True
        self.a.session.seeks.remove(self)
        self.expired_time = time.time()

    def __str__(self):
        return self._str

# vim: expandtab tabstop=4 softtabstop=4 shiftwidth=4 smarttab autoindent
