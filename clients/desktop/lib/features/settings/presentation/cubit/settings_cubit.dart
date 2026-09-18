import 'package:equatable/equatable.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/constants.dart';
import '../../../../core/network/dio_client.dart';
import '../../../../core/theme/design_system.dart';
import '../../../../core/theme/magnus_theme.dart';

class SettingsState extends Equatable {
  const SettingsState({
    required this.design,
    required this.daemonUrl,
    required this.hasToken,
    required this.appearance,
    required this.fontFamily,
    required this.useSystemAccent,
  });

  final DesignSystem design;
  final String daemonUrl;

  /// Solo se expone si hay token, nunca su valor.
  final bool hasToken;
  final Appearance appearance;
  final String fontFamily;
  final bool useSystemAccent;

  SettingsState copyWith({
    DesignSystem? design,
    String? daemonUrl,
    bool? hasToken,
    Appearance? appearance,
    String? fontFamily,
    bool? useSystemAccent,
  }) =>
      SettingsState(
        design: design ?? this.design,
        daemonUrl: daemonUrl ?? this.daemonUrl,
        hasToken: hasToken ?? this.hasToken,
        appearance: appearance ?? this.appearance,
        fontFamily: fontFamily ?? this.fontFamily,
        useSystemAccent: useSystemAccent ?? this.useSystemAccent,
      );

  @override
  List<Object?> get props =>
      [design, daemonUrl, hasToken, appearance, fontFamily, useSystemAccent];
}

/// Gestiona el diseño elegido (Windows/Material/Apple), la URL y el token del
/// daemon, persistiéndolos en disco. Cambiar el diseño re-renderiza toda la app.
class SettingsCubit extends Cubit<SettingsState> {
  SettingsCubit(this._prefs, this._dio)
      : super(SettingsState(
          // Si no hay diseño guardado, autodetecta por la plataforma del equipo.
          design: DesignSystem.fromName(
            _prefs.getString(AppConstants.prefDesignSystem),
            fallback: DesignSystem.forPlatform(defaultTargetPlatform),
          ),
          daemonUrl: _prefs.getString(AppConstants.prefDaemonUrl) ?? AppConstants.defaultDaemonUrl,
          hasToken: (_prefs.getString(AppConstants.prefDaemonToken) ?? '').isNotEmpty,
          appearance: Appearance.fromName(_prefs.getString(AppConstants.prefAppearance)),
          fontFamily: _prefs.getString(AppConstants.prefFont) ?? AppConstants.defaultFont,
          useSystemAccent:
              _prefs.getBool(AppConstants.prefUseSystemAccent) ?? false,
        )) {
    _dio.baseUrl = state.daemonUrl;
    _dio.token = _prefs.getString(AppConstants.prefDaemonToken);
  }

  final SharedPreferences _prefs;
  final DioClient _dio;

  Future<void> setDesign(DesignSystem design) async {
    await _prefs.setString(AppConstants.prefDesignSystem, design.name);
    emit(state.copyWith(design: design));
  }

  Future<void> setAppearance(Appearance appearance) async {
    await _prefs.setString(AppConstants.prefAppearance, appearance.name);
    emit(state.copyWith(appearance: appearance));
  }

  Future<void> setFont(String fontFamily) async {
    await _prefs.setString(AppConstants.prefFont, fontFamily);
    emit(state.copyWith(fontFamily: fontFamily));
  }

  Future<void> setUseSystemAccent(bool value) async {
    await _prefs.setBool(AppConstants.prefUseSystemAccent, value);
    emit(state.copyWith(useSystemAccent: value));
  }

  Future<void> setDaemonUrl(String url) async {
    final clean = url.trim();
    await _prefs.setString(AppConstants.prefDaemonUrl, clean);
    _dio.baseUrl = clean;
    emit(state.copyWith(daemonUrl: clean));
  }

  /// Guarda el token (vacío = quitarlo). Va en las preferencias de la app: en la
  /// beta no se usa el llavero del sistema porque flutter_secure_storage exige
  /// ATL en Windows y rompía la compilación.
  Future<void> setDaemonToken(String token) async {
    final clean = token.trim();
    if (clean.isEmpty) {
      await _prefs.remove(AppConstants.prefDaemonToken);
    } else {
      await _prefs.setString(AppConstants.prefDaemonToken, clean);
    }
    _dio.token = clean;
    emit(state.copyWith(hasToken: clean.isNotEmpty));
  }
}
