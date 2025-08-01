Handling Slay the Spire game data
=================================

.. module:: src.gamedata

.. autoclass:: BaseNode
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: NeowBonus
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: all_bonuses,all_costs
   :inherited-members:

   This class handles everything to do with the Neow bonus.
   Some of the run-specific data will only be available if
   RunHistoryPlus is installed when the run is first started.
   In the absence of the mod, a sane default will be returned.

.. autoclass:: ShopContents
   :members:
   :undoc-members:
   :inherited-members:
   :exclude-members: bar,graph
