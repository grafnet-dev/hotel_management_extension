import { registry } from "@web/core/registry";
import { AppState } from "../store";

const SERVICE_NAME = "hm_reception_store";
// (facultatif) actions centralisées
function createActions(state) {
  return {
    //actions

    // Créer une nouvelle réservation avec une liste vide de stays.
    addBooking(booking) {
      const id = Date.now(); // ou un ID temporaire
      const newBooking = {
        id,
        client_id: booking.client_id,
        date_start: booking.date_start,
        date_end: booking.date_end,
        stay_ids: [], // on lie plus tard
      };
      state.reservations.bookings.push(newBooking);
      return id;
    },

    // Ajouter un séjour à une réservation, enrichir, calculer les totaux.
    addStay(bookingId, stayData) {
      const id = Date.now(); // ID unique temporaire
      const stay = {
        id,
        booking_id: bookingId,
        room_id: stayData.room_id,
        check_in: stayData.check_in,
        check_out: stayData.check_out,
        food_lines: [],
        event_lines: [],
        service_lines: [],
      };

      // enrichir (détails, totaux)
      const enriched = this.enrichStay(stay);

      state.reservations.stays.push(enriched);

      // lier le séjour à la réservation
      const booking = state.reservations.bookings.find(
        (b) => b.id === bookingId
      );
      if (booking) {
        booking.stay_ids.push(enriched.id);
      }

      return enriched.id;
    },

    // Ajouter room info, totaux.
    enrichStay(stay) {
      const room = state.rooms.list.find((r) => r.id === stay.room_id);

      const room_price_total = this.calculateStayTotals(stay, room);

      return {
        ...stay,
        room_details: room,
        room_price_total,
        consumption_total: 0, // sera calculé plus tard avec consommations
        total_amount: room_price_total, // total global
      };
    },

    // Calcule le prix de la chambre en fonction des dates.
    calculateStayTotals(stay, room) {
      const inDate = new Date(stay.check_in);
      const outDate = new Date(stay.check_out);
      const nights = Math.ceil((outDate - inDate) / (1000 * 60 * 60 * 24));
      return nights * room.price;
    },
  };
}

registry.category("services").add(SERVICE_NAME, {
  start() {
    const state = AppState;
    console.log("🧪 [STORE] AppState before reactive", state);

    const actions = createActions(state);
    console.log("🧪 [STORE] State and actions returned from store:", {
      state,
      actions,
    });

    // On expose `state` (observable) + les actions
    return {
      state,
      ...actions,
    };
  },
});
