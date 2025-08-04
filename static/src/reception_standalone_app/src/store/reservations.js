import { reactive } from "@odoo/owl";

export const ReservationStore = reactive({
  bookings: [],  // chaque réservation avec client, date, liste de stay_ids
  stays: [],     // chaque séjour individuel (lié à une chambre)
  foodBookingLines: [],
  eventBookingLines: [],
  serviceBookingLines: [],
});
