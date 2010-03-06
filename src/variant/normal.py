"""This implements routines for normal chess.  (I avoid the term
standard since that is used to describe the game speed on FICS.)
Maybe normal chess technically not a variant, but organizationally
I didn't want to privilege it over variants, so it is here. """

import re
import copy
from array import array

from variant import Variant
import globals
    
"""
0x88 board representation; pieces are represented as ASCII,
the same as FEN. A blank square is '-'.

"""

[A8, B8, C8, D8, E8, F8, G8, H8] = range(0x70, 0x78)
[A7, B7, C7, D7, E7, F7, G7, H7] = range(0x60, 0x68)
[A6, B6, C6, D6, E6, F6, G6, H6] = range(0x50, 0x58)
[A5, B5, C5, D5, E5, F5, G5, H5] = range(0x40, 0x48)
[A4, B4, C4, D4, E4, F4, G4, H4] = range(0x30, 0x38)
[A3, B3, C3, D3, E3, F3, G3, H3] = range(0x20, 0x28)
[A2, B2, C2, D2, E2, F2, G2, H2] = range(0x10, 0x18)
[A1, B1, C1, D1, E1, F1, G1, H1] = range(0x00, 0x08)

class BadFenError(Exception):
    pass
class IllegalMoveError(Exception):
    def __init__(self, reason):
        self.reason = reason

piece_moves = {
    'n': [-0x21, -0x1f, -0xe, -0x12, 0x12, 0xe, 0x1f, 0x21],
    'b': [-0x11, -0xf, 0xf, 0x11],
    'r': [-0x10, -1, 1, 0x10],
    'q': [-0x11, -0xf, 0xf, 0x11, -0x10, -1, 1, 0x10],
    'k': [-0x11, -0xf, 0xf, 0x11, -0x10, -1, 1, 0x10]
}
direction_table = array('i', [0 for i in range(0, 0x100)])
def dir(fr, to):
    """Returns the direction a queen needs to go to get from TO to FR,
    or 0 if it's not possible."""
    return direction_table[to - fr + 0x7f]

sliding_pieces = frozenset(['b', 'r', 'q', 'B', 'R', 'Q'])

piece_material = {
    '-': 0,
    'p': 1,
    'n': 3,
    'b': 3,
    'r': 5,
    'q': 9,
    'k': 0
}

def to_castle_flags(w_oo, w_ooo, b_oo, b_ooo):
    return w_oo << 3 + w_ooo << 2 + b_oo << 1 + b_ooo

def check_castle_flags(mask, wtm, is_oo):
    return mask & (1 << (2 * int(wtm) + int(is_oo)))

castle_mask = array('i', [0 for i in range(0x80)])
castle_mask[A8] = to_castle_flags(True, True, True, False)
castle_mask[E8] = to_castle_flags(True, True, False, False)
castle_mask[H8] = to_castle_flags(True, True, False, True)
castle_mask[A1] = to_castle_flags(True, False, True, True)
castle_mask[E1] = to_castle_flags(False, False, True, True)
castle_mask[H1] = to_castle_flags(False, True, True, True)

def rank(sq):
    return sq / 0x10

def file(sq):
    return sq % 8

def valid_sq(sq):
    return not (sq & 0x88)

def str_to_sq(s):
    return 'abcdefgh'.index(s[0]) + 0x10 * '12345678'.index(s[1])

def sq_to_str(sq):
    return 'abcdefgh'[file(sq)] + '12345678'[rank(sq)]

def piece_is_white(pc):
    assert(len(pc) == 1)
    assert(pc in 'pnbrqkPNBRQK')
    return pc.isupper()

class Move(object):
    def __init__(self, pos, fr, to, prom=None, is_oo=False, is_ooo=False):
        self.pos = pos
        self.fr = fr
        self.to = to
        self.pc = self.pos.board[self.fr]
        self.prom = prom
        self.is_oo = is_oo
        self.is_ooo = is_ooo
        self.is_capture = pos.board[to] != '-'
        self.new_ep = None

    def check_pseudo_legal(self):
        """Tests if a move is pseudo-legal, that is, legal ignoring the
        fact that the king cannot be left in check. Also sets en passant
        flags for this move."""
        diff = self.to - self.fr
        if self.pc == 'p':
            if self.pos.board[self.to] == '-':
                if diff == -0x10:
                    return True
                elif diff == -0x20 and rank(self.fr) == 6:
                    self.new_ep = self.fr + -0x10
                    return self.pos.board[self.new_ep] == '-'
                elif self.to == self.pos.ep:
                    return True
                else:
                    return False
            else:
                return diff in [-0x11, -0xf]
        elif self.pc == 'P':
            if self.pos.board[self.to] == '-':
                if diff == 0x10:
                    return True
                elif diff == 0x20 and rank(self.fr) == 1:
                    self.new_ep = self.fr + 0x10
                    return self.pos.board[self.new_ep] == '-'
                elif self.to == self.pos.ep:
                    return True
                else:
                    return False
            else:
                return diff in [0x11, 0xf]
        else:
            if self.pc in sliding_pieces:
                d = dir(self.fr, self.to)
                if d == 0 or not d in piece_moves[self.pc.lower()]:
                    # the piece cannot make that move
                    return False
                # now check if there are any pieces in the way
                for d in piece_moves[self.pc.lower()]:
                    cur_sq = self.fr + d
                    while cur_sq != self.to:
                        if self.pos.board[cur_sq] != '-':
                            return False
                        cur_sq += d
                    return True
            else:
                return self.to - self.fr in piece_moves[self.pc.lower()]

    def is_legal(self):
        if self.is_oo:
            return (not self.pos.in_check
                and check_castle_flags(self.pos.castle_flags,
                    self.pos.wtm, True)
                and self.pos.board[self.fr + 1] == '-'
                and not self.pos.under_attack(self.fr + 1, not self.pos.wtm)
                and not self.pos.under_attack(self.to, not self.pos.wtm))

        if self.is_ooo:
            return (not self.pos.in_check
                and check_castle_flags(self.pos.castle_flags,
                    self.pos.wtm, False)
                and self.pos.board[self.fr - 1] == '-'
                and not self.pos.under_attack(self.fr - 1, not self.pos.wtm)
                and not self.pos.under_attack(self.to, not self.pos.wtm))

        if not self.check_pseudo_legal():
            return False

        legal = True
        self.pos.make_move(self)
        if self.pos.under_attack(self.pos.kpos[int(not self.pos.wtm)],
                self.pos.wtm):
            legal = False
        self.pos.undo_move(self)
        return legal

class Undo(object):
    """information needed to undo a move"""
    pass

class Position(object):
    def __init__(self, fen):
        # XXX make an array
        self.board = 0x80 * ['-']
        # indexed by 2 * wtm + i, where i=0 for O-O and i=1 for O-O-O
        self.castle_flags = 0
        self.kpos = [None, None]
        self.set_pos(fen)

    def attempt_move(self, mv):
        """Raises IllegalMoveError when appropriate."""

        if mv.pc == '-' or piece_is_white(mv.pc) != self.wtm:
            raise IllegalMoveError('can only move own pieces: ' + mv.pc + ';' + sq_to_str(mv.fr))

        topc = self.board[mv.to]
        if topc != '-' and piece_is_white(topc) == self.wtm:
            raise IllegalMoveError('cannot capture own piece')

        if not mv.is_legal():
            raise IllegalMoveError('is not legal')

        self.make_move(mv)
        self._detect_check()

    def set_pos(self, fen):
        """Set the position from Forsyth-Fdwards notation.  The format
        is intentionally interpreted strictly; better to give the user an
        error than take in bad data."""
        try:
            # rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
            m = re.match(r'''^([1-8rnbqkpRNBQKP/]+) ([wb]) ([kqKQ]+|-) ([a-h][36]|-) (\d+) (\d+)$''', fen)
            if not m:
                raise BadFenError()
            (pos, side, castle_flags, ep, fifty_count, full_moves) = [
                m.group(i) for i in range(1, 7)]

            ranks = pos.split('/')
            ranks.reverse()
            self.material = [0, 0]
            for (r, rank) in enumerate(ranks):
                sq = 0x10 * r
                for c in rank:
                    d = '12345678'.find(c)
                    if d > 0:
                        sq += d + 1
                    else:
                        assert(valid_sq(sq))
                        self.board[sq] = c
                        self.material[int(piece_is_white(c))] += \
                            piece_material[c.lower()]
                        if c == 'k':
                            if self.kpos[0] != None:
                                # multiple kings
                                raise BadFenError()
                            self.kpos[0] = sq
                        elif c == 'K':
                            if self.kpos[1] != None:
                                # multiple kings
                                raise BadFenError()
                            self.kpos[1] = sq
                        sq += 1
                if sq & 0xf != 8:
                    # wrong row length
                    raise BadFenError()

            if None in self.kpos:
                # missing king
                raise BadFenError()

            self.wtm = side == 'w'

            # This doesn't give an error on repeated flags (like "qq"),
            # but I think that's OK, since it's still unambiguous.
            self.castle_flags = to_castle_flags('K' in castle_flags,
                'Q' in castle_flags, 'k' in castle_flags, 'q' in castle_flags)

            if ep == '-':
                self.ep = None
            else:
                self.ep = ep[0].index('abcdefgh') + \
                    0x10 * ep[1].index('012345678')
            
            self.fifty_count = int(fifty_count, 10)
            self.half_moves = 2 * (int(full_moves, 10) - 1) + int(not self.wtm)

            self._detect_check()

        except AssertionError:
            raise
        # Usually I don't like using a catch-all except, but it seems to
        # be the safest default action because the FEN is supplied by
        # the user.
        #except:
            #raise BadFenError()

    def __iter__(self):
        for r in range(0, 8):
            for f in range(0, 8):
                sq = 0x10 * r + f
                yield (sq, self.board[sq])

    def to_fen(self):
        pos_str = ''
        for (sq, pc) in self:
            pos_str += pc
        stm_str = 'w' if self.wtm else 'b'
        castling = ''
        if self.castle_flags[2]:
            castling += 'K'
        if self.castle_flags[3]:
            castling += 'Q'
        if self.self.castle_flags[0]:
            castling += 'k'
        if self.black_castle_flags[1]:
            castling += 'q'
        if castling == '':
            castling = '-'

        if self.ep == None:
            ep_str = '-'
        else:
            ep_str = chr(ord('a') + ep)
            if self.wtm:
                ep_str += '3'
            else:
                ep_str += '6'
        full_moves = self.half_moves / 2 + 1
        return "%s %s %s %s %d %d" % (pos_str, stm_str, castling, ep_str, self.fifty_count, full_moves)
    
    def make_move(self, mv):
        """make the move"""
        self.wtm = not self.wtm
        self.half_moves += 1

        mv.undo = Undo()
        mv.undo.cap = self.board[mv.to]
        mv.undo.ep = self.ep
        mv.undo.in_check = self.in_check
        mv.undo.castle_flags = self.castle_flags
        mv.undo.fifty_count = self.fifty_count

        self.board[mv.fr] = '-'
        self.board[mv.to] = mv.pc if not mv.prom else mv.prom

        if mv.pc == 'k':
            self.kpos[0] = mv.to
        elif mv.pc == 'k':
            self.kpos[1] = mv.to

        if mv.new_ep:
            self.ep = mv.new_ep
        else:
            self.ep = None

        if mv.pc in ['p', 'P'] or mv.undo.cap != '-':
            self.fifty_count = 0
        else:
            self.fifty_count += 1

        self.castle_flags &= castle_mask[mv.fr] & castle_mask[mv.to]
    
    def undo_move(self, mv):
        """undo the move"""
        self.wtm = not self.wtm
        self.half_moves -= 1
        self.ep = mv.undo.ep
        self.board[mv.to] = mv.undo.cap
        self.board[mv.fr] = mv.pc
        self.in_check = mv.undo.in_check
        self.fifty_count = mv.undo.fifty_count
        
        if mv.pc == 'k':
            self.kpos[0] = mv.fr
        elif mv.pc == 'k':
            self.kpos[1] = mv.fr

    def _detect_check(self):
        self.in_check = self.under_attack(self.kpos[int(self.wtm)],
            not self.wtm)
    
    def _is_pc_at(self, pc, sq):
        return valid_sq(sq) and self.board[sq] == pc

    def under_attack(self, sq, wtm):
        # pawn attacks
        if wtm:
            if (self._is_pc_at('P', sq + -0x11)
                    or self._is_pc_at('P', sq + -0xf)):
                return True
        else:
            if (self._is_pc_at('p', sq + 0x11)
                    or self._is_pc_at('p', sq + 0xf)):
                return True

        #  knight attacks
        npc = 'N' if wtm else 'n'
        for d in piece_moves['n']:
            if self._is_pc_at(npc, sq + d):
                return True

        # king attacks
        kpc = 'K' if wtm else 'k'
        for d in piece_moves['k']:
            if self._is_pc_at(kpc, sq + d):
                return True

        # bishop/queen attacks
        for d in piece_moves['b']:
            cur_sq = sq
            while valid_sq(cur_sq):
                if self.board[cur_sq] != '-':
                    if wtm:
                        if self.board[cur_sq] in ['B', 'Q']:
                            return True
                    else:
                        if self.board[cur_sq] in ['b', 'q']:
                            return True
                    # square blocked
                    break
                cur_sq += d


        # rook/queen attacks
        for d in piece_moves['r']:
            cur_sq = sq
            while valid_sq(cur_sq):
                if self.board[cur_sq] != '-':
                    if wtm:
                        if self.board[cur_sq] in ['R', 'Q']:
                            return True
                    else:
                        if self.board[cur_sq] in ['r', 'q']:
                            return True
                    # square blocked
                    break
                cur_sq += d

        return False

class Normal(Variant):
    """normal chess"""
    def __init__(self, game):
        self.game = game
        self.pos = copy.deepcopy(initial_pos)

    def do_move(self, s, conn):
        """Try to parse a move and execute it.  If it looks like a move but
        is erroneous or illegal, raise an exception.  Return True if
        the move was handled, or False if it does not look like a move
        and should be processed further."""

        mv = None

        m = re.match(r'([a-h][1-8])([a-h][1-8])(?:=([NBRQ]))?', s)
        if m:
            fr = str_to_sq(m.group(1))
            to = str_to_sq(m.group(2))
            prom = m.group(3)
            if prom == None:
                mv = Move(self.pos, fr, to)
            else:
                if self.pos.wtm:
                    mv = Move(self.pos, fr, to, prom=prom.upper())
                else:
                    mv = Move(self.pos, fr, to, prom=prom.lower())

        if not mv and s in ['O-O', 'OO']:
            if self.pos.wtm:
                mv = Move(self.pos, E1, G1, is_oo=True)
            else:
                mv = Move(self.pos, E8, G8, is_ooo=True)
        
        if not mv and s in ['O-O-O', 'OOO']:
            if self.pos.wtm:
                mv = Move(self.pos, E1, C1, is_oo=True)
            else:
                mv = Move(self.pos, E8, C8, is_ooo=True)

        if mv:
            if not conn.user.session.is_white == self.pos.wtm:
                #conn.write('user %d, wtm %d\n' % conn.user.session.is_white, self.pos.wtm)
                conn.write(_('It is not your move.\n'))
            else:
                try:
                    self.pos.attempt_move(mv)
                except IllegalMoveError as e:
                    conn.write('Illegal move (%s)\n' % s)
                else:
                    s12 = self.to_style12()
                    self.game.white.user.write(s12)
                    self.game.black.user.write(s12)

        return mv != None
    
    def to_style12(self):
        """returns a style12 string"""
        # <12> rnbqkbnr pppppppp -------- -------- -------- -------- PPPPPPPP RNBQKBNR W -1 1 1 1 1 0 473 GuestPPMD GuestCWVQ -1 1 0 39 39 60000 60000 1 none (0:00.000) none 1 0 0
        board_str = ''
        for r in range(7, -1, -1):
            board_str += ' '
            for f in range(8):
                board_str += self.pos.board[0x10 * r + f]
        side_str = 'W' if self.pos.wtm else 'B'
        ep = -1 if not self.pos.ep else file(self.pos.ep)
        w_oo = int(check_castle_flags(self.pos.castle_flags, True, True))
        w_ooo = int(check_castle_flags(self.pos.castle_flags, True, False))
        b_oo = int(check_castle_flags(self.pos.castle_flags, False, True))
        b_ooo = int(check_castle_flags(self.pos.castle_flags, False, False))
        relation = 1
        full_moves = self.pos.half_moves / 2 + 1
        last_move_time_str = '(%d:%06.3f)' % (self.game.last_move_mins,
            self.game.last_move_secs)
        # board_str begins with a space
        s = '<12>%s %s %d %d %d %d %d %d %d %s %s %d %d %d %d %d %d %d %d %s %s %s %d' % (
            board_str, side_str, ep, w_oo, w_ooo, b_oo, b_ooo,
            self.pos.fifty_count, self.game.number, self.game.white.user.name,
            self.game.black.user.name, relation, self.game.white.time,
            self.game.white.inc, self.pos.material[1], self.pos.material[0],
            self.game.white_clock, self.game.black_clock,
            full_moves, self.game.last_move_verbose, last_move_time_str,
            self.game.last_move_san, int(self.game.flip))
        return s

def init_direction_table():
    for r in range(8):
        for f in range(8):
            sq = 0x10 * r + f
            for d in piece_moves['q']:
                cur_sq = sq + d
                while valid_sq(cur_sq):
                    assert(0 <= cur_sq - sq + 0x7f <= 0xff)
                    if direction_table[cur_sq - sq + 0x7f] != 0:
                        assert(d == direction_table[cur_sq - sq + 0x7f])
                    else:
                        direction_table[cur_sq - sq + 0x7f] = d
                    cur_sq += d
init_direction_table()

initial_pos = Position('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')

# vim: expandtab tabstop=4 softtabstop=4 shiftwidth=4 smarttab autoindent
