import { reactive } from "@odoo/owl";

export const ReservationTypeStore = reactive({
  list: [],
});
console.log("📦 [Reservation_Type] Reservation_type list:", ReservationTypeStore.list);