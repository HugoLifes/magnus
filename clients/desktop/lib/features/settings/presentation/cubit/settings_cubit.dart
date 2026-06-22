import 'package:equatable/equatable.dart';
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
    required this.appearance,
  });

  final DesignSystem design;
  final String daemonUrl;
  final Appearance appearance;

  SettingsState copyWith({
    DesignSystem? design,
    String? daemonUrl,
    Appearance? appearance,
  }) =>
      SettingsState(
        design: design ?? this.design,
        daemonUrl: daemonUrl ?? this.daemonUrl,
        appearance: appearance ?? this.appearance,
      );

  @override
  List<Object?> get props => [design, daemonUrl, appearance];
}

/// Gestiona el diseño elegido (Windows/Material/Apple) y la URL del daemon,
/// persistiéndolos en disco. Cambiar el diseño re-renderiza toda la app.
class SettingsCubit extends Cubit<SettingsState> {
  SettingsCubit(this._prefs, this._dio)
      : super(SettingsState(
          design: DesignSystem.fromName(_prefs.getString(AppConstants.prefDesignSystem)),
          daemonUrl: _prefs.getString(AppConstants.prefDaemonUrl) ?? AppConstants.defaultDaemonUrl,
          appearance: Appearance.fromName(_prefs.getString(AppConstants.prefAppearance)),
        )) {
    _dio.baseUrl = state.daemonUrl;
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

  Future<void> setDaemonUrl(String url) async {
    final clean = url.trim();
    await _prefs.setString(AppConstants.prefDaemonUrl, clean);
    _dio.baseUrl = clean;
    emit(state.copyWith(daemonUrl: clean));
  }
}
