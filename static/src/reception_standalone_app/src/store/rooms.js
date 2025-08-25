import { reactive } from "@odoo/owl";
import { roomTypes } from "../data/rooms";

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

export const RoomStore = reactive({
  list: deepClone(roomTypes), 
});
console.log("📦 [RoomStore] Room list:", RoomStore.list);
