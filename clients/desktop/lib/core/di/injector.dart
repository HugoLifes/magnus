import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../features/models/data/datasources/magnus_remote_datasource.dart';
import '../../features/models/data/repositories/magnus_repository_impl.dart';
import '../../features/models/domain/repositories/magnus_repository.dart';
import '../../features/models/domain/usecases.dart';
import '../../features/models/presentation/bloc/models_bloc.dart';
import '../../features/settings/presentation/cubit/settings_cubit.dart';
import '../network/dio_client.dart';

final sl = GetIt.instance;

/// Registra todo el grafo de dependencias. Llamar una vez en `main()` antes de
/// runApp. El orden importa: externos -> red -> data -> domain -> presentación.
Future<void> initDependencies() async {
  // Externos
  final prefs = await SharedPreferences.getInstance();
  sl.registerSingleton<SharedPreferences>(prefs);

  // Red (singleton: una sola instancia de Dio compartida y reconfigurable)
  sl.registerSingleton<DioClient>(DioClient());

  // Data
  sl.registerLazySingleton<MagnusRemoteDataSource>(() => MagnusRemoteDataSource(sl()));
  sl.registerLazySingleton<MagnusRepository>(() => MagnusRepositoryImpl(sl()));

  // Domain (casos de uso)
  sl.registerLazySingleton(() => GetHardware(sl()));
  sl.registerLazySingleton(() => GetModels(sl()));
  sl.registerLazySingleton(() => CheckCompatibility(sl()));
  sl.registerLazySingleton(() => GetQuantMatrix(sl()));

  // Presentación
  sl.registerFactory(() => ModelsBloc(
        getHardware: sl(),
        getModels: sl(),
        getQuantMatrix: sl(),
      ));
  sl.registerLazySingleton(() => SettingsCubit(sl(), sl()));
}
