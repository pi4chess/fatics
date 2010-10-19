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

from test import *

class TestObserve(Test):
    def test_observe_and_unobserve(self):
        t = self.connect_as('GuestABCD', '')
        t2 = self.connect_as('GuestEFGH', '')
        t3 = self.connect_as('GuestIJKL', '')

        t.write('set style 12\n')
        t.write('observe\n')
        self.expect('Usage:', t)
        t.write('unobserve\n')
        self.expect('You are not observing any games', t)

        t.write('observe GuestABCD\n')
        self.expect('GuestABCD is not playing or examining a game', t)

        t.write('unobserve GuestABCD\n')
        self.expect('GuestABCD is not playing or examining a game', t)

        t.write('observe admin\n')
        self.expect('No player named "admin" is online', t)

        t2.write('match guestijkl 1 0 w\n')
        self.expect('Challenge:', t3)
        t3.write('a\n')
        self.expect('Creating:', t2)
        self.expect('Creating:', t3)

        t2.write('o 1\n')
        self.expect('You cannot observe yourself', t2)
        t3.write('o 1\n')
        self.expect('You cannot observe yourself', t3)

        t.write('o Guestijkl\n')
        self.expect('<12>', t)

        t2.write('h4\n')
        self.expect('<12>', t)
        self.expect('P/h2-h4', t)

        t.write('unobserve\n')
        self.expect('Removing game 1 from observation list.', t)
        t.write('unobserve guestefgh\n')
        self.expect('You are not observing game 1', t)

        t.write('o 1\n')
        self.expect('You are now observing game 1.', t)
        self.expect('Game 1: GuestEFGH (++++) GuestIJKL (++++) unrated lightning 1 0', t)
        self.expect('<12> ', t)
        t.write('o guestefgh\n')
        self.expect('You are already observing game 1.', t)

        t.write('unob 1\n')
        self.expect('Removing game 1 from observation list.', t)
        t.write('ob 1\n')
        self.expect('You are now observing game 1.', t)
        self.expect('<12> ', t)
        t.write('unob Guestefgh\n')
        self.expect('Removing game 1 from observation list.', t)
        t.write('ob guestijkl\n')
        self.expect('You are now observing game 1.', t)
        self.expect('<12> ', t)

        t2.write('res\n')
        self.expect('GuestEFGH resigns} 0-1', t)
        self.expect('Removing game 1 from observation list.', t)

        self.close(t)
        self.close(t2)
        self.close(t3)

    def test_observe_examined(self):
        t = self.connect_as('GuestABCD', '')
        t2 = self.connect_as('GuestEFGH', '')
        t2.write('set style 12\n')

        t.write('ex\n')
        self.expect('Starting a game', t)
        t2.write('o guestabcd\n')
        self.expect('You are now observing game 1.', t2)
        self.expect('Game 1: GuestABCD (0) GuestABCD (0) unrated untimed 0 0', t2)
        self.expect('<12> ', t2)

        t.write('e4\n')
        self.expect('<12> rnbqkbnr pppppppp -------- -------- ----P--- -------- PPPP-PPP RNBQKBNR B -1 1 1 1 1 0 1 GuestABCD GuestABCD -2 0 0 39 39 0 0 1 P/e2-e4 (0:00) e4 0 0 0', t2)

        t.write('unex\n')
        self.expect('GuestABCD has stopped examining game 1.', t2)
        self.expect('Game 1 (which you were observing) has no examiners.', t2)
        self.expect('Removing game 1 from observation list.', t2)

        self.close(t)
        self.close(t2)

    def test_unobserve_logout(self):
        """ Test that games are implicitly unobserved when logging out. """
        t = self.connect_as('GuestABCD', '')
        t2 = self.connect_as('GuestEFGH', '')
        t3 = self.connect_as('GuestIJKL', '')

        t2.write('match guestijkl 1 0 w\n')
        self.expect('Challenge:', t3)
        t3.write('a\n')
        self.expect('Creating:', t2)
        self.expect('Creating:', t3)

        t.write('o guestefgh\n')
        self.expect('You are now observing', t)

        t.write('quit\n')
        self.expect('Removing game 1 from observation list.', t)
        t.close()

        self.close(t2)
        self.close(t3)

    def test_unobserve_multiple(self):
        t = self.connect_as('GuestABCD', '')
        t2 = self.connect_as('GuestEFGH', '')
        t3 = self.connect_as('GuestIJKL', '')
        t4 = self.connect_as('GuestMNOP', '')
        t5 = self.connect_as_guest()

        t.write('match guestefgh 1+0\n')
        self.expect('Challenge:', t2)
        t2.write('a\n')
        self.expect('Creating:', t)

        t3.write('match guestmnop 15+5 chess960\n')
        self.expect('Challenge:', t4)
        t4.write('a\n')
        self.expect('Creating:', t3)

        t5.write('o guestabcd\n')
        self.expect('You are now observing game 1', t5)
        t5.write('o guestmnop\n')
        self.expect('You are now observing game 2', t5)

        t5.write('unob\n')
        self.expect('Removing game 1 from observation list.', t5)
        self.expect('Removing game 2 from observation list.', t5)

        t.write('abort\n')
        t3.write('abort\n')

        for tt in [t, t2, t3, t4, t5]:
            self.close(tt)

class TestAllobservers(Test):
    def test_allobservers(self):
        t = self.connect_as('GuestABCD', '')
        t2 = self.connect_as('GuestEFGH', '')
        t3 = self.connect_as('GuestIJKL', '')
        t4 = self.connect_as('GuestMNOP', '')

        self.expect_command_prints_nothing("allobservers\n", t)

        t2.write('allob 1\n')
        self.expect('There is no such game', t2)

        t2.write('allob nosuchuser\n')
        self.expect('No player named "nosuchuser" is online', t2)

        t2.write('allob i18n\n')
        self.expect('"i18n" is not a valid handle', t2)

        t2.write('allob guestabcd\n')
        self.expect('GuestABCD is not playing or examining a game', t2)

        t.write('match guestefgh 1 0 w\n')
        self.expect('Challenge:', t2)
        t2.write('a\n')
        self.expect('Creating:', t)
        self.expect('Creating:', t2)

        t3.write('match guestmnop 1 0 w\n')
        self.expect('Challenge:', t4)
        t4.write('a\n')
        self.expect('Creating:', t3)
        self.expect('Creating:', t4)

        self.expect_command_prints_nothing("allobservers\n", t)

        t.write('o 2\n')
        self.expect('now observing', t)
        t3.write('o 1\n')
        self.expect('now observing', t3)
        t.write('allob\n')
        self.expect('Observing 1 [GuestABCD vs. GuestEFGH]: GuestIJKL(U) (1 user)', t)
        self.expect('Observing 2 [GuestIJKL vs. GuestMNOP]: GuestABCD(U) (1 user)', t)

        t4.write('o 1\n')
        self.expect('now observing', t4)
        t.write('allob guestefgh\n')
        self.expect('Observing 1 [GuestABCD vs. GuestEFGH]: GuestIJKL(U) GuestMNOP(U) (2 users)', t)
        t2.write('allob 1\n')
        self.expect('Observing 1 [GuestABCD vs. GuestEFGH]: GuestIJKL(U) GuestMNOP(U) (2 users)', t2)
        t3.write('unob guestabcd\n')
        self.expect('Removing', t3)
        t4.write('unob 1\n')
        self.expect('Removing', t4)
        t.write('allob 1\n')
        self.expect('No one is observing game 1.', t)

        self.close(t)
        self.close(t2)
        self.close(t3)
        self.close(t4)

class TestPrimary(Test):
    @with_player('testobs', 'testpass')
    def test_primary(self):
        t = self.connect_as('GuestABCD', '')
        t2 = self.connect_as('GuestEFGH', '')
        t3 = self.connect_as('GuestIJKL', '')
        t4 = self.connect_as('GuestMNOP', '')
        t5 = self.connect_as('testobs', 'testpass')

        t5.write('primary\n')
        self.expect('You are not observing any games.', t5)

        t5.write('primary 1\n')
        self.expect('There is no such game.', t5)

        t.write('ex\n')
        self.expect('Starting a game', t)

        t2.write('match guestijkl 2+12\n')
        self.expect('Challenge:', t3)
        t3.write('a\n')
        self.expect('Creating:', t2)

        t4.write('ex\n')
        self.expect('Starting a game', t4)

        t5.write('o 1\n')
        self.expect('now observing game 1', t5)
        t5.write('o 2\n')
        self.expect('now observing game 2', t5)
        t5.write('o 3\n')
        self.expect('now observing game 3', t5)

        t5.write('primary 1\n')
        t5.write('allobs 1\n')
        self.expect('Game 1 is already your primary game.', t5)
        t5.write('primary guestabcd\n')
        self.expect('Game 1 is already your primary game.', t5)

        t5.write('ki kibitz testing 123\n')
        t5.write('allobs 1\n')
        self.expect('kibitz testing 123', t)

        t5.write('pri 3\n')
        self.expect('Game 3 is now your primary game.', t5)
        t5.write('ki kibitz testing 456\n')
        self.expect('kibitz testing 456', t4)

        t5.write('pri guestefgh\n')
        self.expect('Game 2 is now your primary game.', t5)
        t5.write('ki kibitz testing 789\n')
        self.expect('kibitz testing 789', t2)

        t2.write('abort\n')
        self.expect('aborted on move 1', t5)
        t5.write('ki kibitz testing 987\n')
        self.expect('kibitz testing 987', t4)

        #t.write('primary\n') TODO

        t.write('unex\n')
        t4.write('unex\n')

        for tt in [t, t2, t3, t4, t5]:
            self.close(tt)

# vim: expandtab tabstop=4 softtabstop=4 shiftwidth=4 smarttab autoindent
