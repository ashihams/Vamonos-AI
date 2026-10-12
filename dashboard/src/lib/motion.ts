import type { Transition, Variants } from "framer-motion";

export const EXPO_OUT = [0.16, 1, 0.3, 1] as const;

export const quick: Transition = { duration: 0.2, ease: EXPO_OUT };
export const standard: Transition = { duration: 0.3, ease: EXPO_OUT };
export const entrance: Transition = { duration: 0.6, ease: EXPO_OUT };

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: entrance },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  show: { opacity: 1, scale: 1, transition: entrance },
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

export const inView = { once: true, amount: 0.15 } as const;
