import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/constants.dart';
import '../../../../core/network/dio_client.dart';
import '../../../../core/theme/design_system.dart';

class SettingsState extends Equatable {
  const SettingsState({required this.design, required this.daemonUrl});

  final DesignSystem design;
  final String daemonUrl;

  SettingsState copyWith({DesignSystem? design, String? daemonUrl}) =>
      SettingsState(
        design: design ?? this.design,
        daemonUrl: daemonUrl ?? this.daemonUrl,
      );

  @override
  List<Object?> get props => [design, daemonUrl];
}

/// Gestiona el diseño elegido (Windows/Material/Apple) y la URL del daemon,
/// persistiéndolos en disco. Cambiar el diseño re-renderiza toda la app.
class SettingsCubit extends Cubit<SettingsState> {
  SettingsCubit(this._prefs, this._dio)
      : super(SettingsState(
          design: DesignSystem.fromName(_prefs.getString(AppConstants.prefDesignSystem)),
          daemonUrl: _prefs.getString(AppConstants.prefDaemonUrl) ?? AppConstants.defaultDaemonUrl,
        )) {
    _dio.baseUrl = state.daemonUrl;
  }

  final SharedPreferences _prefs;
  final DioClient _dio;

  Future<void> setDesign(DesignSystem design) async {
    await _prefs.setString(AppConstants.prefDesignSystem, design.name);
    emit(state.copyWith(design: design));
  }

  Future<void> setDaemonUrl(String url) async {
    final clean = url.trim();
    await _prefs.setString(AppConstants.prefDaemonUrl, clean);
    _dio.baseUrl = clean;
    emit(state.copyWith(daemonUrl: clean));
  }
}
