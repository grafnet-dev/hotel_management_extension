import { reactive } from "@odoo/owl";
import { clients as initialClients } from "../data/clients";

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

export const ClientStore = reactive({
  list: deepClone(initialClients), // Liste des clients, clonée pour éviter les mutations directes
  selectedClientId: null, 
  filters: {
    searchText: "",
    membershipStatus: null,
    tierLevel: null,
  },
});
console.log("📦 [ClientStore] Clients List:", ClientStore.list);