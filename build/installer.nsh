!macro customUnInstall
  ; Este diálogo solo aparece en una desinstalación normal, nunca al actualizar Omniverse.
  ${ifNot} ${isUpdated}
    MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "¿Quieres eliminar también todos los datos de Omniverse? Esto incluye proyectos, personajes, acontecimientos, imágenes, base de datos y componentes locales de Python. Esta acción no se puede deshacer. $\r$\n$\r$\nSelecciona No para desinstalar el programa y conservar tus datos." IDYES omniverse_delete_user_data IDNO omniverse_keep_user_data

    omniverse_delete_user_data:
      DetailPrint "Eliminando los datos locales de Omniverse..."
      ; Carpetas de datos que electron-builder y Electron utilizan para esta aplicación.
      RMDir /r "$APPDATA\${APP_FILENAME}"
      !ifdef APP_PRODUCT_FILENAME
        RMDir /r "$APPDATA\${APP_PRODUCT_FILENAME}"
      !endif
      !ifdef APP_PACKAGE_NAME
        RMDir /r "$APPDATA\${APP_PACKAGE_NAME}"
      !endif
      ; Compatibilidad con carpetas usadas por paquetes anteriores del proyecto.
      RMDir /r "$APPDATA\Omniverse"
      RMDir /r "$APPDATA\omniverse-desktop"
      Goto omniverse_uninstall_data_done

    omniverse_keep_user_data:
      DetailPrint "Se conservaron los datos locales de Omniverse."

    omniverse_uninstall_data_done:
  ${endIf}
!macroend
