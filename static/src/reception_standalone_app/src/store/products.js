import { reactive} from "@odoo/owl";
import { products as initialProducts } from "../data/products"

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}
export const ProductStore = reactive({
    list: deepClone(initialProducts), // Liste des produits, clonée pour éviter les mutations directes
    selectedProductId: null, // ID du produit sélectionné
    filters: {
        searchText: "", // Texte de recherche pour filtrer les produits
        category: null, // Catégorie de produit pour filtrer
    },

})
console.log("📦 [ProductStore] Products List:", ProductStore.list);