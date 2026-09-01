from .version import __version__

from .fmp_bootstrap import activate_streamlit_fmp_secret as _activate_streamlit_fmp_secret  # noqa: E402

# Normalize an already-configured Streamlit FMP secret before any news provider
# is constructed. The helper exposes only presence and never logs the value.
_activate_streamlit_fmp_secret()

from . import data_validation_cleanup as _data_validation_cleanup  # noqa: F401,E402
from .prefilter_compat import install as _install_prefilter_compat  # noqa: E402

_install_prefilter_compat()

from .catalyst_route import install as _install_catalyst_route  # noqa: E402
from .contract_compat import install as _install_contract_compat  # noqa: E402

_install_catalyst_route()
_install_contract_compat()

from .readiness_audit import install as _install_readiness_audit  # noqa: E402

_install_readiness_audit()

from .gs257_runtime import install as _install_gs257_runtime  # noqa: E402

_install_gs257_runtime()

from .gs258_cutover import install as _install_gs258_cutover  # noqa: E402

_install_gs258_cutover()

from .gs259_ui_cleanup import install as _install_gs259_ui_cleanup  # noqa: E402

_install_gs259_ui_cleanup()

from .gs261_provenance import install as _install_gs261_provenance  # noqa: E402

_install_gs261_provenance()

from .gs262_discovery_fidelity import install as _install_gs262_discovery_fidelity  # noqa: E402

_install_gs262_discovery_fidelity()

from .gs263_discovery_gate import install as _install_gs263_discovery_gate  # noqa: E402

_install_gs263_discovery_gate()

from .gs285_fmp_latency import install as _install_gs285_fmp_latency  # noqa: E402

_install_gs285_fmp_latency()

from .gs288_fmp_filtering import install as _install_gs288_fmp_filtering  # noqa: E402

_install_gs288_fmp_filtering()

from .gs289_fmp_stock_news_contract import install as _install_gs289_fmp_stock_news_contract  # noqa: E402

_install_gs289_fmp_stock_news_contract()

from .gs292_reevaluation_continuity import install as _install_gs292_reevaluation_continuity  # noqa: E402

_install_gs292_reevaluation_continuity()

from .gs294_fresh_attention_recheck import install as _install_gs294_fresh_attention_recheck  # noqa: E402

_install_gs294_fresh_attention_recheck()

from .gs295_escalation_patch import install as _install_gs295_escalation_patch  # noqa: E402

_install_gs295_escalation_patch()

from .gs296_first_print_alert_patch import install as _install_gs296_first_print_alert_patch  # noqa: E402

_install_gs296_first_print_alert_patch()

from .gs298_news_seeded_discovery import install as _install_gs298_news_seeded_discovery  # noqa: E402

_install_gs298_news_seeded_discovery()

from .gs299_news_reaction_watch import install as _install_gs299_news_reaction_watch  # noqa: E402

_install_gs299_news_reaction_watch()

from .gs300_fmp_news_pagination import install as _install_gs300_fmp_news_pagination  # noqa: E402

_install_gs300_fmp_news_pagination()

from .gs301_catalyst_evidence_handoff import install as _install_gs301_catalyst_evidence_handoff  # noqa: E402

_install_gs301_catalyst_evidence_handoff()

from .gs302_stage_purity_enforcement import install as _install_gs302_stage_purity_enforcement  # noqa: E402

_install_gs302_stage_purity_enforcement()

from .gs303_flight_recorder_authoritative_funnel import install as _install_gs303_flight_recorder_authoritative_funnel  # noqa: E402

_install_gs303_flight_recorder_authoritative_funnel()

from .gs304_fresh_evidence_readiness_guard import install as _install_gs304_fresh_evidence_readiness_guard  # noqa: E402

_install_gs304_fresh_evidence_readiness_guard()

from .gs305_second_wave_attention import install as _install_gs305_second_wave_attention  # noqa: E402

_install_gs305_second_wave_attention()

from .gs307_volume_regime_patch import install as _install_gs307_volume_regime_patch  # noqa: E402

_install_gs307_volume_regime_patch()

from .gs309_current_attention_mission import install as _install_gs309_current_attention_mission  # noqa: E402

_install_gs309_current_attention_mission()

from .gs310_unified_opportunity_state import install as _install_gs310_unified_opportunity_state  # noqa: E402

_install_gs310_unified_opportunity_state()

from .gs311_unified_voice import install as _install_gs311_unified_voice  # noqa: E402

_install_gs311_unified_voice()

from .gs323_direct_user_activation_voice import install as _install_gs323_direct_user_activation_voice  # noqa: E402

_install_gs323_direct_user_activation_voice()

from .gs312_scan_stage_timing import install as _install_gs312_scan_stage_timing  # noqa: E402

_install_gs312_scan_stage_timing()

from .gs313_restart_scan_guard import install as _install_gs313_restart_scan_guard  # noqa: E402

_install_gs313_restart_scan_guard()

from .gs314_state_consistency import install as _install_gs314_state_consistency  # noqa: E402

_install_gs314_state_consistency()

from .gs315_news_intelligence import install as _install_gs315_news_intelligence  # noqa: E402

_install_gs315_news_intelligence()

from .gs316_morning_mover_attention_balance import install as _install_gs316_morning_mover_attention_balance  # noqa: E402

_install_gs316_morning_mover_attention_balance()

from .gs326_near_miss_watch import install as _install_gs326_near_miss_watch  # noqa: E402

_install_gs326_near_miss_watch()

from .gs330_compact_operator_status import install as _install_gs330_compact_operator_status  # noqa: E402

_install_gs330_compact_operator_status()

from .gs331_scroll_safe_area import install as _install_gs331_scroll_safe_area  # noqa: E402

_install_gs331_scroll_safe_area()

from .gs332_action_first_radar import install as _install_gs332_action_first_radar  # noqa: E402

_install_gs332_action_first_radar()

from .gs333_extreme_mover_operator_priority import install as _install_gs333_extreme_mover_operator_priority  # noqa: E402

_install_gs333_extreme_mover_operator_priority()

from .gs334_market_event_lane import install as _install_gs334_market_event_lane  # noqa: E402

_install_gs334_market_event_lane()

from .gs336_early_session_reset_watch import install as _install_gs336_early_session_reset_watch  # noqa: E402

_install_gs336_early_session_reset_watch()

from .gs338_momentum_ignition_transition import install as _install_gs338_momentum_ignition_transition  # noqa: E402

_install_gs338_momentum_ignition_transition()

from .gs339_preignition_vwap_reclaim import install as _install_gs339_preignition_vwap_reclaim  # noqa: E402

_install_gs339_preignition_vwap_reclaim()

from .gs340_high_liquidity_trend_watch import install as _install_gs340_high_liquidity_trend_watch  # noqa: E402

_install_gs340_high_liquidity_trend_watch()

from .gs344_emergence_convergence_engine import install as _install_gs344_emergence_convergence_engine  # noqa: E402

_install_gs344_emergence_convergence_engine()

from .gs345_persistent_leader_escalation import install as _install_gs345_persistent_leader_escalation  # noqa: E402

_install_gs345_persistent_leader_escalation()

from .gs347_native_radar_timeout_health import install as _install_gs347_native_radar_timeout_health  # noqa: E402

_install_gs347_native_radar_timeout_health()

from .gs348_st_vwap_operator_priority import install as _install_gs348_st_vwap_operator_priority  # noqa: E402

_install_gs348_st_vwap_operator_priority()

from .gs349_operator_first_layout import install as _install_gs349_operator_first_layout  # noqa: E402

_install_gs349_operator_first_layout()

from .gs350_download_export_reliability import install as _install_gs350_download_export_reliability  # noqa: E402

_install_gs350_download_export_reliability()

from .gs351_session_rerun_isolation import install as _install_gs351_session_rerun_isolation  # noqa: E402

_install_gs351_session_rerun_isolation()

from .gs352_persistent_alert_arm import install as _install_gs352_persistent_alert_arm  # noqa: E402

_install_gs352_persistent_alert_arm()

from .gs353_entry_lock_clarity import install as _install_gs353_entry_lock_clarity  # noqa: E402

_install_gs353_entry_lock_clarity()
