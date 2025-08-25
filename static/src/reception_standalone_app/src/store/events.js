import { reactive} from "@odoo/owl";
import { events as initialEvents } from "../data/events"

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}
export const EventsStore = reactive({
    list: deepClone(initialEvents), // Liste des produits, clonée pour éviter les mutations directes
    selectedEventId: null, // ID de l'événement sélectionné
    filters: {
        searchText: "", // Texte de recherche pour filtrer les événements
        category: null, // Catégorie d'événement pour filtrer
    },

})
console.log("📦 [EventsStore] Events List:", EventsStore.list);