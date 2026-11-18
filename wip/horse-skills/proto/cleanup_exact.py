"""Prototype: exact level-30 cleanup.

The cleanup swaps unwanted skills until every wanted skill is held. Today's rule (bdo.horses / sim_fast) keeps
re-swapping the same slot until it gives a wanted skill, which depends on history. For an exact table the rule must
depend only on the skills held; candidate: "always swap the rarest unwanted skill held" (rule 'rarest').

G(S, p)[c] = chance that the cleanup, starting from held skills S with p Skill Change Points, gets every wanted
skill using at most c coupons (c = 0..C). Swaps keep the number of skills, wanted skills are never removed, and p
grows by one per coupon, so G is computed layer by layer from the highest p down.
"""
import random

import numpy as np


class Cleanup:
    def __init__(self, w, wmask, order, rare, point_bonus=0.25):
        self.w, self.wmask, self.order, self.rare, self.pb = list(w), wmask, list(order), list(rare), point_bonus
        self.n = len(w)
        self.full = (1 << self.n) - 1

    def slot(self, S):
        """rule 'rarest': the rarest unwanted skill held (-1 if none)"""
        for i in self.order:
            if S >> i & 1 and not self.wmask >> i & 1:
                return i
        return -1

    def transitions(self, S, p, out):
        """[(next S, probability)] for swapping skill 'out' out of S with p points"""
        w, n = self.w, self.n
        free = ~S & ~(1 << out) & self.full
        target = next((i for i in self.rare if free >> i & 1), -1)
        boost = 1 + self.pb * p
        ws = [(i, w[i] * boost if i == target else w[i]) for i in range(n) if free >> i & 1]
        tot = sum(x for _, x in ws)
        return [((S & ~(1 << out)) | (1 << i), x / tot) for i, x in ws]

    def table(self, starts, C):
        """Exact G for every (S, p) reachable from the start states [(S, p)] within C coupons.
        Returns dict (S, p) -> numpy array of length C + 1."""
        layers = {}                                   # p -> set of S
        frontier = set(starts)
        seen = set()
        depth = {}
        for s in starts:
            depth[s] = 0
        while frontier:
            nxt = set()
            for S, p in frontier:
                if (S, p) in seen:
                    continue
                seen.add((S, p))
                layers.setdefault(p, set()).add(S)
                if S & self.wmask == self.wmask or depth[(S, p)] >= C:
                    continue
                out = self.slot(S)
                if out < 0:
                    continue
                for S2, _ in self.transitions(S, p, out):
                    key = (S2, p + 1)
                    d = depth[(S, p)] + 1
                    if key not in depth or d < depth[key]:
                        depth[key] = d
                    if key not in seen:
                        nxt.add(key)
            frontier = nxt
        G = {}
        zero = np.zeros(C + 1)
        for p in sorted(layers, reverse=True):
            for S in layers[p]:
                if S & self.wmask == self.wmask:
                    G[(S, p)] = np.ones(C + 1)
                    continue
                out = self.slot(S)
                g = np.zeros(C + 1)
                if out >= 0:
                    for S2, pr in self.transitions(S, p, out):
                        nx = G.get((S2, p + 1), zero)
                        g[1:] += pr * nx[:-1]
                G[(S, p)] = g
        return G

    def mc_needed(self, S, p, rng, rule="rarest", cap=10**6):
        """Monte Carlo: coupons used until every wanted skill is held (None if impossible)."""
        n_w = bin(self.wmask).count("1")
        if bin(S).count("1") < n_w:
            return None
        used = 0
        if rule == "rarest":
            while S & self.wmask != self.wmask and used < cap:
                out = self.slot(S)
                S = _pick(self.transitions(S, p, out), rng)
                p += 1
                used += 1
        else:                                        # today's rule: re-swap the same slot until it's wanted
            for q in [i for i in self.order if S >> i & 1 and not self.wmask >> i & 1]:
                slot = q
                while not self.wmask >> slot & 1 and S & self.wmask != self.wmask and used < cap:
                    S2 = _pick(self.transitions(S, p, slot), rng)
                    slot = (S2 & ~S).bit_length() - 1
                    S = S2
                    p += 1
                    used += 1
                if S & self.wmask == self.wmask:
                    break
        return used if S & self.wmask == self.wmask else None


def _pick(trans, rng):
    x = rng.random()
    for S2, pr in trans:
        x -= pr
        if x < 0:
            return S2
    return trans[-1][0]
