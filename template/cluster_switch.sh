function ic-cluster {
    alias runai=runai-ic
    # This is actually changing the context not the cluster ...
    runai config cluster ic-caas
    runai config project mlo-$GASPAR_USERNAME
}

function rcp-cluster {
    alias runai=runai-rcp
    # This is actually changing the context not the cluster ...
    runai config cluster rcp-caas
    runai config project mlo-$GASPAR_USERNAME
}
