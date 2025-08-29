/** @odoo-module **/

/**
 * Fonction générique pour appeler une méthode Odoo via RPC
 * @param {string} model - Nom du modèle Odoo (ex: "hotel.booking.stay")
 * @param {string} method - Nom de la méthode (ex: "create_stay_from_ui")
 * @param {Array} args - Arguments positionnels passés à la méthode
 * @param {Object} kwargs - Arguments nommés (optionnel)
 * @returns {Promise<any>} - Résultat de l'appel RPC
 */

import { rpc } from "@web/core/network/rpc";

export async function methodCall(model, method, args = [], kwargs = {}) {
  try {
    const result = await rpc("/web/dataset/call_kw/", {
      model,
      method,
      args,
      kwargs,
    });
    return result;
  } catch (error) {
    console.error(`❌ RPC Error [${model}.${method}]`, error);
    throw error;
  }
}
