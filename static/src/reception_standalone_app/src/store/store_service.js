/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

const store = reactive({ count: 0 });

const StoreService = {
  start() {
    console.log("🛠️ StoreService started");
    return {
      getCount: () => store.count,
      increment: () => {
        store.count += 1;
        console.log("🧮 Compteur mis à jour:", store.count);
      },
    };
  },
};

registry.category("services").add("store", StoreService);
