// Statuts possibles
export const BOOKING_STATUS = {
  PENDING: "pending",
  CONFIRMED: "confirmed",
  IN_PROGRESS: "in_progress",
  COMPLETED: "completed",
  CANCELLED: "cancelled",
};

export const STAY_STATUS = {
  PENDING: "pending",
  CHECKED_IN: "checked_in",
  CHECKED_OUT: "checked_out",
  CANCELLED: "cancelled",
};

// Transitions autorisées
export const bookingTransitions = {
  [BOOKING_STATUS.PENDING]: [
    BOOKING_STATUS.CONFIRMED,
    BOOKING_STATUS.CANCELLED,
  ],
  [BOOKING_STATUS.CONFIRMED]: [
    BOOKING_STATUS.IN_PROGRESS,
    BOOKING_STATUS.CANCELLED,
  ],
  [BOOKING_STATUS.IN_PROGRESS]: [
    BOOKING_STATUS.COMPLETED,
    BOOKING_STATUS.CANCELLED,
  ],
  [BOOKING_STATUS.COMPLETED]: [],
  [BOOKING_STATUS.CANCELLED]: [],
};

export const stayTransitions = {
  [STAY_STATUS.PENDING]: [STAY_STATUS.CHECKED_IN, STAY_STATUS.CANCELLED],
  [STAY_STATUS.CHECKED_IN]: [STAY_STATUS.CHECKED_OUT, STAY_STATUS.CANCELLED],
  [STAY_STATUS.CHECKED_OUT]: [],
  [STAY_STATUS.CANCELLED]: [],
};
