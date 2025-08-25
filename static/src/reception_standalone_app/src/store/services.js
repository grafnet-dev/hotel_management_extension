import { reactive} from "@odoo/owl";
import { services as initialServices } from "../data/services"

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}
export const ServicesStore = reactive({
    list: deepClone(initialServices), // Liste des produits, clonée pour éviter les mutations directes
    selectedServiceId: null, // ID du service sélectionné
    filters: {
        searchText: "", // Texte de recherche pour filtrer les services
        category: null, // Catégorie de service pour filtrer
    },

})
console.log("📦 [ServicesStore] Products List:", ServicesStore.list);