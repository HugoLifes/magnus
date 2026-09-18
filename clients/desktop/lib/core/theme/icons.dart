import 'package:fluentui_system_icons/fluentui_system_icons.dart';
import 'package:flutter/cupertino.dart' show CupertinoIcons;
import 'package:flutter/material.dart' show Icons;
import 'package:flutter/widgets.dart';

import 'design_system.dart';
import 'magnus_theme.dart';

/// Iconos por significado, no por nombre de set.
///
/// Cada diseño usa el set de su plataforma, que es lo que hace que la app se
/// sienta nativa: **Fluent** en Windows, **Material Symbols** (redondeados) en
/// Android y los de **SF/Cupertino** en Apple. Las páginas piden
/// `MagnusIcons.of(context).chat` y no saben de qué set salió.
class MagnusIcons {
  const MagnusIcons.forDesign(this.design);

  final DesignSystem design;

  static MagnusIcons of(BuildContext context) =>
      MagnusIcons.forDesign(MagnusTheme.of(context).design);

  IconData _pick(IconData windows, IconData material, IconData apple) =>
      switch (design) {
        DesignSystem.windows => windows,
        DesignSystem.material => material,
        DesignSystem.apple => apple,
      };

  /// En Material 3 un destino sin seleccionar va en contorno y el activo
  /// relleno. En Fluent y SF los iconos ya son de trazo: se devuelven igual.
  IconData unselected(IconData icon) =>
      design == DesignSystem.material ? (_m3Outline[icon] ?? icon) : icon;

  static final _m3Outline = <IconData, IconData>{
    Icons.speed_rounded: Icons.speed_outlined,
    Icons.chat_bubble_rounded: Icons.chat_bubble_outline_rounded,
    Icons.developer_board_rounded: Icons.developer_board_outlined,
    Icons.smart_toy_rounded: Icons.smart_toy_outlined,
    Icons.menu_book_rounded: Icons.menu_book_outlined,
    Icons.monitor_heart_rounded: Icons.monitor_heart_outlined,
    Icons.cloud_rounded: Icons.cloud_outlined,
    Icons.settings_rounded: Icons.settings_outlined,
  };

  // --- Navegación ---------------------------------------------------------
  IconData get dashboard =>
      _pick(FluentIcons.gauge_24_regular, Icons.speed_rounded, CupertinoIcons.speedometer);
  IconData get home =>
      _pick(FluentIcons.home_24_regular, Icons.home_rounded, CupertinoIcons.house);
  IconData get chat => _pick(
      FluentIcons.chat_24_regular, Icons.chat_bubble_rounded, CupertinoIcons.chat_bubble_2);
  IconData get chats => _pick(FluentIcons.chat_multiple_24_regular, Icons.forum_rounded,
      CupertinoIcons.chat_bubble_2_fill);
  IconData get models => _pick(FluentIcons.developer_board_24_regular,
      Icons.developer_board_rounded, CupertinoIcons.cube_box);
  IconData get agents =>
      _pick(FluentIcons.bot_24_regular, Icons.smart_toy_rounded, CupertinoIcons.person_2);
  IconData get documents =>
      _pick(FluentIcons.book_24_regular, Icons.menu_book_rounded, CupertinoIcons.book);
  IconData get resources => _pick(FluentIcons.heart_pulse_24_regular,
      Icons.monitor_heart_rounded, CupertinoIcons.waveform_path_ecg);
  IconData get cloud =>
      _pick(FluentIcons.cloud_24_regular, Icons.cloud_rounded, CupertinoIcons.cloud);
  IconData get settings =>
      _pick(FluentIcons.settings_24_regular, Icons.settings_rounded, CupertinoIcons.gear);

  // --- Acciones -----------------------------------------------------------
  IconData get download => _pick(FluentIcons.arrow_download_24_regular,
      Icons.download_rounded, CupertinoIcons.cloud_download);
  IconData get play =>
      _pick(FluentIcons.play_24_regular, Icons.play_arrow_rounded, CupertinoIcons.play_arrow);
  IconData get unload => _pick(
      FluentIcons.power_24_regular, Icons.power_settings_new_rounded, CupertinoIcons.power);
  IconData get delete =>
      _pick(FluentIcons.delete_24_regular, Icons.delete_rounded, CupertinoIcons.delete);
  IconData get add =>
      _pick(FluentIcons.add_24_regular, Icons.add_rounded, CupertinoIcons.add);
  IconData get minus =>
      _pick(FluentIcons.subtract_24_regular, Icons.remove_rounded, CupertinoIcons.minus);
  IconData get close =>
      _pick(FluentIcons.dismiss_24_regular, Icons.close_rounded, CupertinoIcons.xmark);
  IconData get check =>
      _pick(FluentIcons.checkmark_24_regular, Icons.check_rounded, CupertinoIcons.checkmark);
  IconData get success => _pick(FluentIcons.checkmark_circle_24_regular,
      Icons.check_circle_rounded, CupertinoIcons.checkmark_circle);
  IconData get search =>
      _pick(FluentIcons.search_24_regular, Icons.search_rounded, CupertinoIcons.search);
  IconData get refresh => _pick(FluentIcons.arrow_sync_24_regular, Icons.refresh_rounded,
      CupertinoIcons.arrow_2_circlepath);
  IconData get save =>
      _pick(FluentIcons.save_24_regular, Icons.save_rounded, CupertinoIcons.floppy_disk);
  IconData get edit =>
      _pick(FluentIcons.edit_24_regular, Icons.edit_rounded, CupertinoIcons.pencil);
  IconData get send =>
      _pick(FluentIcons.send_24_regular, Icons.send_rounded, CupertinoIcons.paperplane);
  IconData get newFolder => _pick(FluentIcons.folder_add_24_regular,
      Icons.create_new_folder_rounded, CupertinoIcons.folder_badge_plus);
  IconData get build =>
      _pick(FluentIcons.wrench_24_regular, Icons.build_rounded, CupertinoIcons.wrench);
  IconData get tune => _pick(
      FluentIcons.options_24_regular, Icons.tune_rounded, CupertinoIcons.slider_horizontal_3);
  IconData get launch => _pick(
      FluentIcons.rocket_24_regular, Icons.rocket_launch_rounded, CupertinoIcons.rocket);
  IconData get choose => _pick(FluentIcons.cursor_click_24_regular, Icons.touch_app_rounded,
      CupertinoIcons.hand_point_right);
  IconData get openExternal => _pick(FluentIcons.open_24_regular, Icons.open_in_new_rounded,
      CupertinoIcons.arrow_up_right_square);
  IconData get chevronRight => _pick(FluentIcons.chevron_right_24_regular,
      Icons.chevron_right_rounded, CupertinoIcons.chevron_right);
  IconData get stepInto => _pick(FluentIcons.arrow_step_in_right_24_regular,
      Icons.subdirectory_arrow_right_rounded, CupertinoIcons.arrow_turn_down_right);
  IconData get eye =>
      _pick(FluentIcons.eye_24_regular, Icons.visibility_rounded, CupertinoIcons.eye);
  IconData get eyeOff => _pick(
      FluentIcons.eye_off_24_regular, Icons.visibility_off_rounded, CupertinoIcons.eye_slash);

  // --- Estado y avisos ----------------------------------------------------
  IconData get warning => _pick(FluentIcons.warning_24_regular, Icons.warning_amber_rounded,
      CupertinoIcons.exclamationmark_triangle);
  IconData get info =>
      _pick(FluentIcons.info_24_regular, Icons.info_rounded, CupertinoIcons.info);
  IconData get tip => _pick(
      FluentIcons.lightbulb_24_regular, Icons.lightbulb_rounded, CupertinoIcons.lightbulb);
  IconData get sparkle => _pick(
      FluentIcons.sparkle_24_regular, Icons.auto_awesome_rounded, CupertinoIcons.sparkles);
  IconData get activity => _pick(FluentIcons.pulse_24_regular, Icons.show_chart_rounded,
      CupertinoIcons.waveform_path_ecg);
  IconData get shield => _pick(
      FluentIcons.shield_error_24_regular, Icons.gpp_maybe_rounded, CupertinoIcons.shield);
  IconData get favorite =>
      _pick(FluentIcons.heart_24_regular, Icons.favorite_rounded, CupertinoIcons.heart);
  IconData get star =>
      _pick(FluentIcons.star_24_regular, Icons.star_rounded, CupertinoIcons.star);
  IconData get forever => _pick(FluentIcons.arrow_repeat_all_24_regular,
      Icons.all_inclusive_rounded, CupertinoIcons.infinite);

  // --- Hardware y datos ---------------------------------------------------
  IconData get gpu => _pick(
      FluentIcons.developer_board_24_regular, Icons.memory_rounded, CupertinoIcons.cube_box);
  IconData get memory =>
      _pick(FluentIcons.hard_drive_24_regular, Icons.storage_rounded, CupertinoIcons.memories);
  IconData get database => _pick(FluentIcons.database_24_regular, Icons.dataset_rounded,
      CupertinoIcons.square_stack_3d_up);
  IconData get layers => _pick(
      FluentIcons.layer_24_regular, Icons.layers_rounded, CupertinoIcons.square_stack_3d_up);
  IconData get temperature => _pick(FluentIcons.temperature_24_regular,
      Icons.thermostat_rounded, CupertinoIcons.thermometer);
  IconData get bolt =>
      _pick(FluentIcons.flash_24_regular, Icons.bolt_rounded, CupertinoIcons.bolt);
  IconData get server =>
      _pick(FluentIcons.server_24_regular, Icons.dns_rounded, CupertinoIcons.desktopcomputer);
  IconData get network =>
      _pick(FluentIcons.globe_24_regular, Icons.lan_rounded, CupertinoIcons.globe);
  IconData get laptop =>
      _pick(FluentIcons.laptop_24_regular, Icons.laptop_rounded, CupertinoIcons.device_laptop);
  IconData get monitor => _pick(FluentIcons.desktop_24_regular,
      Icons.desktop_windows_rounded, CupertinoIcons.desktopcomputer);
  IconData get phone =>
      _pick(FluentIcons.phone_24_regular, Icons.smartphone_rounded, CupertinoIcons.phone);
  IconData get connected =>
      _pick(FluentIcons.plug_connected_24_regular, Icons.link_rounded, CupertinoIcons.link);
  IconData get disconnected => _pick(
      FluentIcons.plug_disconnected_24_regular, Icons.link_off_rounded, CupertinoIcons.link);

  // --- Contenido ----------------------------------------------------------
  IconData get document => _pick(
      FluentIcons.document_24_regular, Icons.description_rounded, CupertinoIcons.doc_text);
  IconData get brain => _pick(
      FluentIcons.brain_circuit_24_regular, Icons.psychology_rounded, CupertinoIcons.memories);
  IconData get calculator => _pick(
      FluentIcons.calculator_24_regular, Icons.calculate_rounded, CupertinoIcons.function);
  IconData get key =>
      _pick(FluentIcons.key_24_regular, Icons.vpn_key_rounded, CupertinoIcons.keyboard);

  // --- Dinero (el ámbar de la marca vive solo aquí) -----------------------
  IconData get credits => _pick(
      FluentIcons.coin_multiple_24_regular, Icons.toll_rounded, CupertinoIcons.creditcard);
  IconData get savings => _pick(
      FluentIcons.wallet_24_regular, Icons.savings_rounded, CupertinoIcons.money_dollar_circle);
  IconData get money => _pick(
      FluentIcons.money_24_regular, Icons.payments_rounded, CupertinoIcons.money_dollar_circle);
  IconData get voucher => _pick(FluentIcons.ticket_diagonal_24_regular,
      Icons.confirmation_number_rounded, CupertinoIcons.ticket);
  IconData get gift =>
      _pick(FluentIcons.gift_24_regular, Icons.card_giftcard_rounded, CupertinoIcons.gift);

  // --- Apariencia ---------------------------------------------------------
  IconData get dark => _pick(
      FluentIcons.weather_moon_24_regular, Icons.dark_mode_rounded, CupertinoIcons.moon);
  IconData get light => _pick(
      FluentIcons.weather_sunny_24_regular, Icons.light_mode_rounded, CupertinoIcons.sun_max);
}

/// Azúcar para las páginas: `context.icons.chat`.
extension MagnusIconsContext on BuildContext {
  MagnusIcons get icons => MagnusIcons.of(this);
}
